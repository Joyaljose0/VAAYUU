import serial
import time
import random
import threading
import socket
import os

# Configuration
PORT = "COM3"
BAUDRATE = 115200
TIMEOUT = 1

ser = None
serial_lock = threading.Lock()
is_warming_up = False

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def send_auto_ip():
    # Check if we are intentionally using a Cloud Backend (Render)
    # We look at the frontend config to see if it's pointing away from localhost
    try:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", ".env.local")
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                content = f.read()
                if "onrender.com" in content or "https://" in content:
                    print("[Serial] Cloud Backend detected in frontend config. Skipping local IP auto-sync to hardware.")
                    return
    except Exception as e:
        print(f"[Serial] Error checking cloud config: {e}")

    ip = get_local_ip()
    if ip != '127.0.0.1':
        print(f"Auto-syncing backend IP via USB: {ip}")
        write_serial(f"UPDATE_IP:{ip}\n")

def connect_serial():
    global ser
    with serial_lock:
        if ser is None or not ser.is_open:
            try:
                ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
                print(f"Successfully connected to {PORT}")
                
                # Wait 3 seconds for ESP32 to finish bootloader, then send our auto IP
                threading.Timer(3.0, send_auto_ip).start()
                
                return True
            except serial.SerialException as e:
                print(f"Warning: Could not connect to {PORT}. Error: {e}")
                ser = None
                return False
        return True

def write_serial(data: str):
    global ser
    with serial_lock:
        if ser and ser.is_open:
            try:
                # Add newline if not present since Serial.readStringUntil('\n') is common
                if not data.endswith('\n'):
                    data += '\n'
                
                # IMPORTANT: Clear output buffers and wait a tiny bit to avoid TX/RX race conditions
                ser.reset_output_buffer()
                time.sleep(0.1)
                
                ser.write(data.encode('utf-8'))
                ser.flush()
                
                # Give it a tiny bit of time to make sure the ESP32 parsed it
                # before the readline() loop kicks back in
                time.sleep(0.2) 
                
                return True
            except Exception as e:
                print(f"Error writing to serial: {e}")
                return False
        return False

# Try initial connection if not on Render cloud
if not os.getenv("RENDER"):
    connect_serial()
else:
    print("[Serial] Running on Render Cloud. Serial (USB) disabled.")

def read_sensor():
    global ser, is_warming_up
    
    # Try reconnecting if not connected
    if ser is None or not ser.is_open:
        if not connect_serial():
            print("Hardware disconnected or port busy. Waiting...")
            return None
            
    try:
        # Loop to consume boot logs and find the real sensor reading
        for _ in range(10): 
            with serial_lock:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
            if not line:
                continue
                
            if line.startswith("DATA:"):
                # ... same logic ...
                try:
                    payload = line[5:]
                    parts = payload.split(",")
                    if len(parts) >= 6:
                        if len(parts) >= 7:
                            data_vals = list(map(float, parts[1:7]))
                        else:
                            data_vals = list(map(float, parts[:6]))
                            
                        co, gas, temp, hum, pres, o2 = data_vals
                        
                        return {
                            "co": co,
                            "gas": gas,
                            "temperature": temp,
                            "humidity": hum,
                            "pressure": pres,
                            "oxygen": o2,
                            "is_warming_up": is_warming_up
                        }
                except (ValueError, IndexError) as e:
                    print(f"Skipping malformed data frame: {line} ({e})")
                    continue
            elif line.startswith("STATUS:"):
                if "WARMING_UP" in line:
                    is_warming_up = True
                elif "READY" in line:
                    is_warming_up = False
                print(f"DEVICE STATUS: {line}")
                continue
            else:
                if line:
                    print(f"ESP32 INFO: {line}")
                continue
                
        # If we looped 10 times and still didn't find good data
        return None
        
            
    except Exception as e:
        print(f"Error reading from sensor: {e}")
        # Mark serial as broken so it tries to reconnect next time
        with serial_lock:
            if ser:
                try:
                    ser.close()
                except:
                    pass
                ser = None
        return None