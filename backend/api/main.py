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
from ml.lstm_predict import predict_escape, get_ai_metrics
from api.alerts import check_alerts
import threading
import socket
import time
from collections import deque
from ml.train_from_csv import train_model, MODES
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

# Shared control states
latest_data = {}
data_lock = threading.Lock()
# Auto-switch to WIFI mode if running on Render
connection_mode = "WIFI" if os.getenv("RENDER") else "USB" 
env_mode = "BUILDING"   
shutdown_event = threading.Event()

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
                    # AI Trend Analysis
                    inference_buffer_usb.append(sensor)
                    escape_time = predict_escape(list(inference_buffer_usb), env_mode)
                    
                    alerts, safety_score, ttu = check_alerts(
                        sensor["oxygen"],
                        sensor["co"],
                        sensor["gas"],
                        sensor["temperature"],
                        sensor["humidity"],
                        env_mode,
                        list(inference_buffer_usb)
                    )
                    print(f"Hardware Data Received ({env_mode}) -> Temp: {sensor['temperature']}°C | CO: {sensor['co']}ppm | O2: {sensor['oxygen']}%")

                    # Thread-safe dictionary swap
                    with data_lock:
                        latest_data.clear()
                        latest_data.update({
                            **sensor,
                            "escape_time": escape_time if not sensor.get("is_warming_up") else None,
                            "ttu_estimate": ttu if not sensor.get("is_warming_up") else None,
                            "safety_score": safety_score if not sensor.get("is_warming_up") else 100,
                            "backend_alerts": alerts if not sensor.get("is_warming_up") else [],
                            "ai_metrics": get_ai_metrics(),
                            "last_updated": int(time.time()),
                            "env_mode": env_mode # Track active mode
                        })

                    # Trigger physical buzzer via Serial if hazardous
                    if alerts and (safety_score <= 80 or any("CRITICAL" in a or "Severe" in a for a in alerts)):
                        if not sensor.get("is_warming_up"):
                            print("[Serial] Hazard Detected! Sending BUZZ command.")
                            write_serial("BUZZ\n")

                    # Format alerts or say 'no'
                    alert_text = "|".join(alerts) if alerts else "no"

                    # --- Prevent Stale Data Logging ---
                    with data_lock:
                        last_updated = latest_data.get("last_updated", 0)
                    
                    if time.time() - last_updated < 5.0:
                        csv_data = [
                            sensor["co"],
                            sensor["gas"],
                            sensor["temperature"],
                            sensor["humidity"],
                            sensor["pressure"],
                            sensor["oxygen"],
                            alert_text,
                            escape_time # Store prediction in CSV for future tuning
                        ]
                        
                        log_to_csv(csv_data, env_mode)
            
            time.sleep(1)

    def periodic_training_loop():
        """Periodic background training thread for BOTH modes."""
        while not shutdown_event.is_set():
            try:
                # Wait 5 minutes between training
                for _ in range(300):
                    if shutdown_event.is_set(): return
                    time.sleep(1)
                
                print("[AI] Starting periodic background retraining...")
                for mode in ["BUILDING", "VEHICLE"]:
                    train_model(mode)
            except Exception as e:
                print(f"[AI] Training Thread Error: {e}")
            
    threading.Thread(target=loop, daemon=True).start()
    
    if not os.getenv("RENDER"):
        threading.Thread(target=periodic_training_loop, daemon=True).start()
    
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
        data_copy["env_mode"] = env_mode
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
        print(f"\n[MODE CHANGE] Environment set to: {env_mode}")
        return {"status": "success", "mode": env_mode}
    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail="Invalid environment mode")

@app.post("/train")
def trigger_training(data: EnvMode):
    """Force a training run for a specific mode."""
    if data.mode in MODES:
        def run_training():
            try:
                print(f"[AI] Manual training triggered for {data.mode}...")
                train_model(data.mode)
            except Exception as e:
                print(f"[AI Error] Manual training failed: {e}")
        
        threading.Thread(target=run_training, daemon=True).start()
        return {"status": "training_started", "mode": data.mode}
    raise HTTPException(status_code=400, detail="Invalid mode for training")

@app.get("/")
def read_root():
    return {"message": "VAAYUU AI Backend is running. Access /live for data."}

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
    global connection_mode, env_mode
    if connection_mode != "WIFI":
        print(f"[Cloud API] Mode Conflict: Switching to WIFI for incoming hardware data.")
        connection_mode = "WIFI"
        
    sensor = data.dict()
    
    # Update inference buffer synchronously for real-time alert check
    inference_buffer_wifi.append(sensor)
    
    # Calculate alerts synchronously so we can tell the buzzer to fire immediately
    alerts, safety_score, ttu = check_alerts(
        sensor["oxygen"],
        sensor["co"],
        sensor["gas"],
        sensor["temperature"],
        sensor["humidity"],
        env_mode,
        list(inference_buffer_wifi)
    )
    
    # Determine if buzzer should sound (Critical or Safety Score <= 80)
    should_buzz = len(alerts) > 0 and (safety_score <= 80 or any("CRITICAL" in a or "Severe" in a for a in alerts))
    
    # Also send via Serial if in USB mode or mixed mode
    if should_buzz and not sensor.get("is_warming_up"):
        write_serial("BUZZ\n")
    
    # Background the logging and voice tasks to keep response fast
    background_tasks.add_task(process_wifi_data, sensor, alerts, safety_score, ttu)
    
    from fastapi import Response
    import json
    resp_body = json.dumps({
        "status": "ok", 
        "env_mode": env_mode,
        "buzzer": should_buzz
    })
    return Response(content=resp_body, media_type='application/json')

def process_wifi_data(sensor, alerts, safety_score, ttu):
    global latest_data
    try:
        # Update dashboard with AI and alert results
        with data_lock:
            latest_data.update({
                **sensor,
                "connection_mode": "WIFI",
                "last_updated": int(time.time()),
                "env_mode": env_mode,
                "escape_time": ttu if not sensor.get("is_warming_up") else None, # Using TTU as proxy for escape
                "ttu_estimate": ttu if not sensor.get("is_warming_up") else None,
                "safety_score": safety_score if not sensor.get("is_warming_up") else 100,
                "backend_alerts": alerts if not sensor.get("is_warming_up") else [],
                "ai_metrics": get_ai_metrics(),
            })
            
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
            ttu # Store ttu in CSV
        ]
        log_to_csv(csv_data, env_mode)

    except Exception as e:
        print(f"[Cloud API ERROR] Critical failure in process_wifi_data: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

