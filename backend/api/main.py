from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hardware.serial_reader import read_sensor, write_serial
from hardware.csv_logger import log_to_csv
from ml.lstm_predict import predict_escape, train_on_live_data, get_ai_metrics
from api.alerts import check_alerts
import threading
import socket
import time
from collections import deque
from ml.train_from_csv import train_model
from pydantic import BaseModel

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

local_ip = get_local_ip()


class WiFiConfig(BaseModel):
    ssid: str
    password: str
    ip: str

class SensorData(BaseModel):
    co: float
    gas: float
    temperature: float
    humidity: float
    pressure: float
    oxygen: float
    is_warming_up: bool = False

# Virtual Oxygen calculation removed to prioritize real hardware calibration accuracy.


# Shared control states
latest_data = {}
data_lock = threading.Lock()
# Auto-switch to WIFI mode if running on Render
connection_mode = "WIFI" if os.getenv("RENDER") else "USB" 
env_mode = "BUILDING"   
shutdown_event = threading.Event()

# Background Training Queue
training_queue = deque(maxlen=60) # Keep max 60 last frames
training_lock = threading.Lock()

# Inference buffers for sequence-based trend analysis
inference_buffer_usb = deque(maxlen=30)
inference_buffer_wifi = deque(maxlen=30)

class ConnectionMode(BaseModel):
    mode: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading, time
    
    def loop():
        global latest_data, connection_mode
        while not shutdown_event.is_set():
            if connection_mode == "USB":
                try:
                    sensor = read_sensor()
                except Exception as e:
                    print(f"Serial Read Error (Expected on Render): {e}")
                    sensor = None
                
                if sensor:
                    # Virtual oxygen removed to prioritize real hardware calibration accuracy.
                    
                    
                    # Trend-based escape prediction using last 30 seconds
                    inference_buffer_usb.append(sensor)
                    escape_time = predict_escape(list(inference_buffer_usb))
                    alerts = check_alerts(
                        sensor["oxygen"],
                        sensor["co"],
                        sensor["gas"],
                        sensor["temperature"],
                        sensor["humidity"],
                        env_mode
                    )
                    print(f"Hardware Data Received -> Temp: {sensor['temperature']}°C | CO: {sensor['co']}ppm | O2: {sensor['oxygen']}%")

                    # Thread-safe dictionary swap
                    with data_lock:
                        latest_data.clear()
                        latest_data.update({
                            **sensor,
                            "escape_time": escape_time if not sensor.get("is_warming_up") else None,
                            "backend_alerts": alerts if not sensor.get("is_warming_up") else [],
                            "ai_metrics": get_ai_metrics(),
                            "last_updated": int(time.time())
                        })

                    # Format alerts or say 'no'
                    alert_text = "|".join(alerts) if alerts else "no"

                    # --- Prevent Stale Data Logging ---
                    # Only log to CSV if the data is fresh (less than 5 seconds old)
                    with data_lock:
                        last_updated = latest_data.get("last_updated", 0)
                    
                    if time.time() - last_updated < 5.0:
                        # Prepare the data array. We exclude escape time as requested
                        csv_data = [
                            sensor["co"],
                            sensor["gas"],
                            sensor["temperature"],
                            sensor["humidity"],
                            sensor["pressure"],
                            sensor["oxygen"],
                            alert_text,
                            escape_time
                        ]
                        
                        log_to_csv(csv_data)
                        
                        with training_lock:
                            training_queue.append(sensor)
            
            # Sleep 1s whether we read data or not (or if we skipped because of WIFI mode)
            time.sleep(1)
            
    def periodic_training_loop():
        """Periodic background training thread (User Request: Every 5-10 minutes)"""
        print("[AI] Periodic Training Thread Started.")
        while not shutdown_event.is_set():
            try:
                # Wait 5 minutes between training (300 seconds)
                for _ in range(300):
                    if shutdown_event.is_set(): return
                    time.sleep(1)
                
                print("[AI] Starting periodic background retraining from CSV...")
                train_model()
            except Exception as e:
                print(f"[AI] Training Thread Error: {e}")

    threading.Thread(target=loop, daemon=True).start()
    
    # Only run training thread if NOT on Render (Free tier 512MB RAM limit)
    if not os.getenv("RENDER"):
        threading.Thread(target=periodic_training_loop, daemon=True).start()
    else:
        print("[AI] Background training DISABLED for Render stability.")
    yield
    print("Shutdown signal received. Stopping background threads...")
    shutdown_event.set()
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/live")
def live_data():
    with data_lock:
        data_copy = latest_data.copy()
        data_copy["connection_mode"] = connection_mode
        data_copy["backend_ip"] = local_ip
        return data_copy

@app.post("/connection-mode")
def set_connection_mode(data: ConnectionMode):
    global connection_mode
    if data.mode in ["USB", "WIFI"]:
        connection_mode = data.mode
        return {"status": "success", "mode": connection_mode}
    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail="Invalid mode")

class EnvMode(BaseModel):
    mode: str

@app.post("/env-mode")
def set_env_mode(data: EnvMode):
    global env_mode
    if data.mode in ["BUILDING", "VEHICLE"]:
        env_mode = data.mode
        print(f"Environment Mode Updated: {env_mode}")
        return {"status": "success", "mode": env_mode}
    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail="Invalid environment mode")

@app.get("/")
def read_root():
    return {"message": "AuraGuard AI Backend is running. Access /live for data."}

class RawCommand(BaseModel):
    command: str

@app.post("/command")
def send_command(cmd: RawCommand):
    success = write_serial(cmd.command + "\n")
    if success:
        return {"status": "success", "message": f"Command '{cmd.command}' sent to device"}
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to send command to device")

@app.post("/config-wifi")
def config_wifi(config: WiFiConfig):
    msg = f"WIFI:{config.ssid},{config.password},{config.ip}\n"
    success = write_serial(msg)
    if success:
        return {"status": "success", "message": "WiFi configuration sent to device"}
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to send configuration to device")

from fastapi import BackgroundTasks

@app.post("/sensor-data")
def receive_sensor_data(data: SensorData, background_tasks: BackgroundTasks):
    print(f"[Cloud API] POST /sensor-data received from {data.co}, {data.gas}")
    if connection_mode != "WIFI":
        print(f"[Cloud API] Warning: Ignoring WiFi data because mode is {connection_mode}")
        return {"status": "ignored", "message": f"Backend is in {connection_mode} mode"}
        
    sensor = data.dict()
    background_tasks.add_task(process_wifi_data, sensor)
    from fastapi import Response
    return Response(content='{"status": "ok"}', media_type='application/json', headers={"Connection": "close"})

def process_wifi_data(sensor):
    global latest_data
    try:
        # STEP 1: Update dashboard immediately with raw sensor data
        with data_lock:
            latest_data.update({
                **sensor,
                "connection_mode": "WIFI",
                "last_updated": int(time.time())
            })
        print(f"[Cloud API] Live Update Sent: Temp={sensor['temperature']}°C")

        # STEP 2: Process heavy AI/Alerts in the background
        inference_buffer_wifi.append(sensor)
        
        start_ai = time.time()
        print("[Cloud AI] Starting prediction...")
        escape_time = predict_escape(list(inference_buffer_wifi))
        ai_duration = time.time() - start_ai
        
        alerts = check_alerts(
            sensor["oxygen"],
            sensor["co"],
            sensor["gas"],
            sensor["temperature"],
            sensor["humidity"],
            env_mode
        )
        
        # STEP 3: Update again with AI results
        with data_lock:
            latest_data.update({
                "escape_time": escape_time if not sensor.get("is_warming_up") else None,
                "backend_alerts": alerts if not sensor.get("is_warming_up") else [],
                "ai_metrics": get_ai_metrics(),
            })
            
        print(f"[Cloud AI] Done in {ai_duration:.2f}s. Prediction: {escape_time}m")

        if not os.getenv("RENDER"):
            with training_lock:
                training_queue.append(sensor)
        
        # Explicitly clear RAM on Render
        import gc
        gc.collect()

        # Logging logic
        alert_text = "|".join(alerts) if alerts else "no"
        csv_data = [
            sensor["co"],
            sensor["gas"],
            sensor["temperature"],
            sensor["humidity"],
            sensor["pressure"],
            sensor["oxygen"],
            alert_text,
            escape_time
        ]
        log_to_csv(csv_data)

    except Exception as e:
        print(f"[Cloud API ERROR] Critical failure in process_wifi_data: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

