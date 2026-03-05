import requests
import time
import os

BASE_URL = "http://localhost:8000"

def test_mode_switch():
    print("Testing Environment Mode Switching...")
    
    # 1. Set to BUILDING
    print("Setting mode to BUILDING...")
    res = requests.post(f"{BASE_URL}/env-mode", json={"mode": "BUILDING"})
    assert res.status_code == 200
    assert res.json()["mode"] == "BUILDING"
    
    # 2. Send some data and check logging
    print("Sending sensor data in BUILDING mode...")
    sensor_data = {
        "co": 5.0,
        "gas": 900.0,
        "temperature": 25.0,
        "humidity": 50.0,
        "pressure": 1013.0,
        "oxygen": 20.5
    }
    requests.post(f"{BASE_URL}/sensor-data", json=sensor_data)
    time.sleep(2) # Wait for background processing
    
    # Check if building CSV exists
    assert os.path.exists("data/air_quality_building.csv")
    print("✓ BUILDING logging verified.")

    # 3. Set to VEHICLE
    print("Setting mode to VEHICLE...")
    res = requests.post(f"{BASE_URL}/env-mode", json={"mode": "VEHICLE"})
    assert res.status_code == 200
    assert res.json()["mode"] == "VEHICLE"
    
    # 4. Send some data and check logging
    print("Sending sensor data in VEHICLE mode...")
    sensor_data["co"] = 12.0 # Higher CO for vehicle test
    requests.post(f"{BASE_URL}/sensor-data", json=sensor_data)
    time.sleep(2)
    
    # Check if vehicle CSV exists
    assert os.path.exists("data/air_quality_vehicle.csv")
    print("✓ VEHICLE logging verified.")

    # 5. Verify prediction routes
    print("Verifying live data environment reflection...")
    res = requests.get(f"{BASE_URL}/live")
    assert res.json()["env_mode"] == "VEHICLE"
    print("✓ Live state verification successful.")

if __name__ == "__main__":
    try:
        test_mode_switch()
        print("\nALL TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
