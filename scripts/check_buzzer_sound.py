import requests
import time

def test_buzzer_sound():
    url = "http://localhost:8000/sensor-data"
    
    # Simulate critical hazardous levels to force the buzzer to trigger
    payload = {
        "co": 500.0,      # Extremely high CO
        "gas": 400.0,
        "temperature": 25.0,
        "humidity": 50.0,
        "pressure": 1013.25,
        "oxygen": 12.0,   # Extremely low O2
        "is_warming_up": False
    }
    
    print("--- STARTING BUZZER SOUND TEST ---")
    print("I will send 3 trigger signals to make the buzzer sound audible.")
    
    for i in range(3):
        print(f"Trigger {i+1}/3...")
        try:
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("buzzer") is True:
                    print("Signal Sent: The buzzer should be BEEPING now.")
                else:
                    print("Signal Sent, but buzzer flag was FALSE. Check backend logic.")
            else:
                print(f"Server Error: {response.status_code}")
        except Exception as e:
            print(f"Connection Error: {e}")
        
        time.sleep(2) # Wait between beeps

    print("--- TEST COMPLETE ---")
    print("If you did not hear anything, ensure the ESP32 is flashed with the new code.")

if __name__ == "__main__":
    test_buzzer_sound()
