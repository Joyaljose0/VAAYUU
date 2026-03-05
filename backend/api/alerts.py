import threading
import queue
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create a queue for speech messages to avoid thread blocking issues
speech_queue = queue.Queue()

def speech_worker():
    # Initialize pyttsx3 ONCE inside the dedicated speech thread (prevents Windows COM exceptions)
    try:
        import pyttsx3
        engine = pyttsx3.init()
        while True:
            msg = speech_queue.get()
            if msg is None: break
            engine.say(msg)
            engine.runAndWait()
            speech_queue.task_done()
    except (Exception, ImportError) as e:
        print(f"Speech engine (pyttsx3) disabled or not available: {e}.")
        # Consume the queue to prevent blocking even if engine is dead
        while True:
            msg = speech_queue.get()
            if msg is None: break
            speech_queue.task_done()

# Start the dedicated speech thread
threading.Thread(target=speech_worker, daemon=True).start()


# Threshold Constants (WHO & OSHA Aligned)
THRESHOLDS = {
    'BUILDING': {
        'o2': {'low': 19.5, 'crit': 17.0, 'fail': 10.0},
        'co': {'elevated': 9, 'unsafe': 35, 'danger': 100, 'crit': 200},
        'co2': {'warn': 800, 'poor': 1000, 'danger': 2500, 'crit': 5000},
        'temp': {'max': 35}
    },
    'VEHICLE': {
        'o2': {'low': 19.5, 'crit': 17.0, 'fail': 10.0},
        'co': {'elevated': 15, 'unsafe': 50, 'danger': 150, 'crit': 400},
        'co2': {'warn': 1000, 'poor': 1200, 'danger': 3000, 'crit': 5000},
        'temp': {'max': 45}
    }
}

def estimate_ttu(o2, co, co2):
    """ Estimates Time-to-Unconsciousness (TTU) in minutes based on physiological data. """
    ttu_points = []

    # 1. Hypoxia (Oxygen Deprivation) - TUC/EPT curves
    if o2 < 6.0: ttu_points.append(0.5) # Immediate collapse
    elif o2 < 10.0: ttu_points.append(1.0)
    elif o2 < 15.0: ttu_points.append(5.0)
    elif o2 < 17.0: ttu_points.append(20.0)
    elif o2 < 19.5: ttu_points.append(60.0)
    else: ttu_points.append(600.0)

    # 2. CO Toxicity (Carboxyhemoglobin lethal levels)
    # Using 3200ppm (~15m), 1600ppm (~45m), 800ppm (~2h)
    if co >= 12800: ttu_points.append(0.2) # 2-3 breaths
    elif co >= 3200: ttu_points.append(10.0)
    elif co >= 1600: ttu_points.append(20.0)
    elif co >= 800: ttu_points.append(45.0)
    elif co >= 400: ttu_points.append(120.0)
    elif co >= 100: ttu_points.append(240.0)
    else: ttu_points.append(600.0)

    # 3. CO2 (Hypercapnia)
    if co2 >= 40000: ttu_points.append(5.0)
    elif co2 >= 10000: ttu_points.append(30.0)
    elif co2 >= 5000: ttu_points.append(120.0)
    else: ttu_points.append(600.0)

    return min(ttu_points)

def calculate_safety_score(o2, co, co2, temp, hum, mode='BUILDING', trends=None):
    """ Calculates a 0-100 safety score based on cumulative risks and environmental stress. """
    score = 100
    t = THRESHOLDS.get(mode, THRESHOLDS['BUILDING'])
    
    ttu = estimate_ttu(o2, co, co2)
    
    # 1. Oxygen (Heavy impact)
    if o2 < 17.0: score -= 50
    elif o2 < 19.5: score -= 20
    
    # 2. Carbon Monoxide (Lethal)
    if co >= t['co']['crit']: score -= 100
    elif co >= t['co']['danger']: score -= 60
    elif co >= t['co']['unsafe']: score -= 30
    elif co >= t['co']['elevated']: score -= 10
    
    # 3. Carbon Dioxide (Cognitive)
    if co2 >= t['co2']['crit']: score -= 80
    elif co2 >= t['co2']['danger']: score -= 40
    elif co2 >= t['co2']['poor']: score -= 20
    elif co2 >= t['co2']['warn']: score -= 5
    
    # 4. Temperature & Humidity (Comfort/Heat Stress)
    if temp > t['temp']['max']: score -= 15
    if hum > 80 or hum < 20: score -= 5

    # 5. Environmental Stress (Trend Analysis)
    if trends:
        # Penalty for rapidly rising toxins
        if trends.get('co_rate', 0) > 1.0: score -= 10 # CO rising >1ppm/sec is alarming
        if trends.get('co2_rate', 0) > 50.0: score -= 10 # CO2 rising >50ppm/sec
    
    # 6. TTU Penalty
    if ttu < 5: score -= 80
    elif ttu < 15: score -= 40
    elif ttu < 60: score -= 10

    return max(0, score)

def check_alerts(o2, co, co2, temp, hum=50, mode='BUILDING', history=None):
    alerts = []
    t = THRESHOLDS.get(mode, THRESHOLDS['BUILDING'])
    
    # Calculate trends and baselines if history is available
    trends = {}
    baseline_co = 0
    baseline_co2 = 400
    
    if history and len(history) >= 5:
        # Use average of early samples as baseline (auto-calibration)
        baseline_co = sum(h.get('co', 0) for h in list(history)[:10]) / min(len(history), 10)
        baseline_co2 = sum(h.get('gas', 400) for h in list(history)[:10]) / min(len(history), 10)
        
        # Calculate rate of change (last sample vs 5 samples ago)
        prev = history[-5]
        trends['co_rate'] = (co - prev.get('co', co)) / 5.0
        trends['co2_rate'] = (co2 - prev.get('gas', co2)) / 5.0
        trends['o2_rate'] = (o2 - prev.get('oxygen', o2)) / 5.0

    ttu = estimate_ttu(o2, co, co2)
    safety_score = calculate_safety_score(o2, co, co2, temp, hum, mode, trends)

    # 1. Oxygen Checks
    if o2 < 10:
        alerts.append("CRITICAL: Oxygen Collapse Risk")
    elif o2 < 14:
        alerts.append("CRITICAL: Oxygen Fainting Risk")
    elif o2 < 17:
        alerts.append("CRITICAL: Oxygen Dizziness (Escape Now)")
    elif o2 < t['o2']['low']:
        alerts.append("Warning: Oxygen Fatigue (Low O2)")
    elif trends.get('o2_rate', 0) < -0.2: # Oxygen dropping faster than 0.2%/sec
        alerts.append("Notice: Oxygen levels dropping rapidly")

    # 2. Carbon Monoxide Checks
    if co >= t['co']['crit']:
        alerts.append("CRITICAL: Fatal CO levels - Life Threatening")
    elif co >= t['co']['danger']:
        alerts.append("CRITICAL: CO Poisoning Emergency")
    elif co >= t['co']['unsafe']:
        alerts.append("Severe: Dangerous CO (Nausea/Fatigue)")
    elif co >= t['co']['elevated']:
        alerts.append("Warning: Elevated CO levels")
    elif co > (baseline_co + 5) and trends.get('co_rate', 0) > 0.5:
        alerts.append("Notice: CO rising significantly above ambient")

    # 3. Carbon Dioxide Checks
    if co2 >= t['co2']['crit']:
        alerts.append("CRITICAL: CO2 Suffocation Risk")
    elif co2 >= t['co2']['danger']:
        alerts.append("Severe: Dangerous CO2 (Sleepiness)")
    elif co2 >= t['co2']['poor']:
        alerts.append("Warning: Poor Air Quality (Fatigue)")
    elif co2 >= t['co2']['warn']:
        alerts.append("Notice: Acceptable CO2 (Mild Drowsiness)")
    elif co2 > (baseline_co2 + 200) and trends.get('co2_rate', 0) > 20.0:
         alerts.append("Notice: CO2 levels increasing rapidly")

    # 4. Temperature Checks
    if temp > t['temp']['max']:
        alerts.append("Warning: Heat Stress Risk")

    # 5. Humidity Checks
    if hum > 70.0:
        alerts.append("Warning: High Humidity (Respiratory Risk)")
    elif hum < 30.0:
        alerts.append("Warning: Low Humidity (Dry Air Discomfort)")

    # 6. Safety Score Alert
    if safety_score < 30:
        alerts.append(f"CRITICAL: SAFETY SCORE {safety_score}% - EVACUATE")
    elif safety_score < 70:
        alerts.append(f"Warning: Poor Safety Score {safety_score}%")

    # 7. TTU Alerts
    if ttu <= 60:
        unit = "minutes" if ttu >= 1 else "seconds"
        val = ttu if ttu >= 1 else ttu * 60
        alerts.append(f"URGENT: Estimated {val} {unit} until unconsciousness")

    if alerts:
        # Non-blocking voice alert
        if speech_queue.empty():
            if ttu < 5:
                # Urgent countdown/warning
                alert_msg = f"Incapacitation in {ttu} minutes. Escape now." if ttu >= 1 else "Incapacitation imminent. Escape immediately."
                speech_queue.put(alert_msg)
            elif safety_score < 40 or "CRITICAL" in "".join(alerts):
                alert_msg = "Danger. Critical levels detected. Escape immediately."
                speech_queue.put(alert_msg)
            elif safety_score < 80:
                # Use trend to predict hazard type
                if trends.get('co_rate', 0) > 0.3: hazard = "carbon monoxide"
                elif trends.get('co2_rate', 0) > 10: hazard = "carbon dioxide"
                elif trends.get('o2_rate', 0) < -0.1: hazard = "oxygen"
                else: hazard = "air quality"
                speech_queue.put(f"Alert. {hazard} levels changing. Check dashboard.")

    return alerts, safety_score, ttu
