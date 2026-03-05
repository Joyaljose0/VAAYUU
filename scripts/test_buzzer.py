import requests
import json

def test_buzzer_logic():
    url = "http://localhost:8000/sensor-data"
    
    # Simulate high CO level to trigger buzzer
    payload = {
        "co": 150.0,
        "gas": 400.0,
        "temperature": 25.0,
        "humidity": 50.0,
        "pressure": 1013.25,
        "oxygen": 20.9,
        "is_warming_up": False
    }
    
    try:
        print(f"Sending high CO payload to {url}...")
        response = requests.post(url, json=payload, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        data = response.json()
        if data.get("buzzer") is True:
            print("SUCCESS: Buzzer flag is TRUE for dangerous CO levels.")
        else:
            print("FAILURE: Buzzer flag is FALSE. Check alert thresholds.")
            
    except Exception as e:
        print(f"Error testing backend: {e}")

if __name__ == "__main__":
    test_buzzer_logic()
