from backend.api.alerts import calculate_safety_score, check_alerts

def test_thresholds():
    print("--- Testing Sensor Thresholds and Safety Score ---")
    
    # 1. Normal Conditions
    print("\n[Test 1] Normal Conditions (O2=20.9, CO=0, CO2=400, Temp=25)")
    score = calculate_safety_score(20.9, 0, 400, 25, 50, 'BUILDING')
    alerts, safety_score, ttu = check_alerts(20.9, 0, 400, 25, 50, 'BUILDING')
    print(f"Safety Score: {safety_score}")
    print(f"TTU Estimate: {ttu} mins")
    print(f"Alerts: {alerts}")
    
    # 2. Critical Oxygen
    print("\n[Test 2] Critical Oxygen (O2=10.0)")
    score = calculate_safety_score(10.0, 0, 400, 25, 50, 'BUILDING')
    alerts, safety_score, ttu = check_alerts(10.0, 0, 400, 25, 50, 'BUILDING')
    print(f"Safety Score: {safety_score}")
    print(f"TTU Estimate: {ttu} mins")
    print(f"Alerts: {alerts}")
    
    # 3. High Carbon Monoxide (Building)
    print("\n[Test 3] High CO in Building (CO=40)")
    score = calculate_safety_score(20.9, 40, 400, 25, 50, 'BUILDING')
    alerts, safety_score, ttu = check_alerts(20.9, 40, 400, 25, 50, 'BUILDING')
    print(f"Safety Score: {safety_score}")
    print(f"Alerts: {alerts}")

    # 4. High Carbon Monoxide (Vehicle) - Should be safer than building for same level
    print("\n[Test 4] High CO in Vehicle (CO=40)")
    score = calculate_safety_score(20.9, 40, 400, 25, 50, 'VEHICLE')
    alerts, safety_score, ttu = check_alerts(20.9, 40, 400, 25, 50, 'VEHICLE')
    print(f"Safety Score: {safety_score}")
    print(f"Alerts: {alerts}")

    # 5. Combined Risks (Moderate CO + Moderate CO2)
    print("\n[Test 5] Combined Risks (CO=20, CO2=1200)")
    score = calculate_safety_score(20.9, 20, 1200, 25, 50, 'BUILDING')
    alerts, safety_score, ttu = check_alerts(20.9, 20, 1200, 25, 50, 'BUILDING')
    print(f"Safety Score: {safety_score}")
    print(f"Alerts: {alerts}")

    # 6. Critical Combined (O2=16, CO=150, CO2=3000)
    print("\n[Test 6] Critical Combined")
    score = calculate_safety_score(16.0, 150, 3000, 25, 50, 'BUILDING')
    alerts, safety_score, ttu = check_alerts(16.0, 150, 3000, 25, 50, 'BUILDING')
    print(f"Safety Score: {safety_score}")
    print(f"TTU Estimate: {ttu} mins")
    print(f"Alerts: {alerts}")

    # 7. Dynamic Trend: Rapidly Rising CO2 (400 -> 1200 in 5 steps)
    print("\n[Test 7] Dynamic Trend: Rapidly Rising CO2 (400 -> 1200 in 5 steps)")
    history = []
    for i in range(5):
        history.append({'co': 0, 'gas': 400 + (i * 100), 'oxygen': 20.9, 'temperature': 25, 'humidity': 50})
    
    # Current sample: 1200 (Rising fast)
    score = calculate_safety_score(20.9, 0, 1200, 25, 50, 'BUILDING', trends={'co2_rate': 100.0})
    # check_alerts will calculate trends internally if history is provided
    alerts, safety_score, ttu = check_alerts(20.9, 0, 1200, 25, 50, 'BUILDING', history=history)
    print(f"Safety Score: {safety_score}")
    print(f"TTU Estimate: {ttu} mins")
    print(f"Alerts: {alerts}")

    # 8. Dynamic Baseline: CO rising above ambient
    print("\n[Test 8] Dynamic Baseline: CO rising above ambient (Ambient=2, Current=10)")
    history = []
    for i in range(10): # Establish baseline of ~2ppm
        history.append({'co': 2, 'gas': 400, 'oxygen': 20.9, 'temperature': 25, 'humidity': 50})
    
    # Current sample: 10
    alerts, safety_score, ttu = check_alerts(20.9, 10, 400, 25, 50, 'BUILDING', history=history)
    print(f"Alerts: {alerts}")

if __name__ == "__main__":
    test_thresholds()
