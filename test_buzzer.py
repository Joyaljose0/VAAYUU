import serial
import time
import sys

try:
    print("Connecting to ESP32 on COM3...")
    ser = serial.Serial('COM3', 115200, timeout=2)
    
    # Wait for ESP32 to reset after serial connection
    time.sleep(2) 
    
    print("Sending BUZZ command...")
    ser.write(b'BUZZ\n')
    ser.flush()
    
    # Give it a moment to process and sound
    time.sleep(1)
    
    print("Test signal sent to GPIO13. Did you hear the buzzer?")
    ser.close()
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
