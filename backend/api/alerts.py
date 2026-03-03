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


# Threshold Constants (Synced with User Physiology Tables)
THRESHOLDS = {
    'BUILDING': {
        'o2_warn': 19.5,   # Fatigue
        'o2_crit': 17.0,   # Dizziness
        'co_elevated': 3,  # Slightly elevated
        'co_unsafe': 10,   # Headache/Dizziness
        'co_danger': 30,   # Nausea/Fatigue
        'co_fatal': 50,    # Serious poisoning
        'co2_warn': 800,   # Mild drowsiness
        'co2_poor': 1000,  # Fatigue/Concentration
        'co2_danger': 1500,# Headache/Sleepiness
        'co2_crit': 5000,  # Oxygen deprivation risk
        'temp_max': 35
    },
    'VEHICLE': {
        'o2_warn': 19.5,
        'o2_crit': 17.0,
        'co_elevated': 5,  # Higher ambient allowance for vehicles
        'co_unsafe': 15,
        'co_danger': 40,
        'co_fatal': 70,
        'co2_warn': 1000,
        'co2_poor': 1200,
        'co2_danger': 2000,
        'co2_crit': 5000,
        'temp_max': 45
    }
}

def check_alerts(o2, co, co2, temp, hum=50, mode='BUILDING'):
    alerts = []
    t = THRESHOLDS.get(mode, THRESHOLDS['BUILDING'])

    # 1. Oxygen Checks (Physiology Table)
    if o2 < 10:
        alerts.append("CRITICAL: Oxygen Collapse Risk")
    elif o2 < 14:
        alerts.append("CRITICAL: Oxygen Fainting Risk")
    elif o2 < 17:
        alerts.append("CRITICAL: Oxygen Dizziness (Escape Now)")
    elif o2 < t['o2_warn']:
        alerts.append("Warning: Oxygen Fatigue (Low O2)")

    # 2. Carbon Monoxide Checks (Physiology Table)
    if co >= 200:
        alerts.append("CRITICAL: Fatal CO levels - Life Threatening")
    elif co >= 50:
        alerts.append("CRITICAL: CO Poisoning Emergency")
    elif co >= t['co_danger']:
        alerts.append("Severe: Dangerous CO (Nausea/Fatigue)")
    elif co >= t['co_unsafe']:
        alerts.append("Warning: Unsafe CO (Headache/Dizziness)")
    elif co >= t['co_elevated']:
        alerts.append("Notice: Slightly elevated CO")

    # 3. Carbon Dioxide Checks (Physiology Table)
    if co2 >= t['co2_crit']:
        alerts.append("CRITICAL: CO2 Suffocation Risk")
    elif co2 >= t['co2_danger']:
        alerts.append("Severe: Dangerous CO2 (Sleepiness)")
    elif co2 >= t['co2_poor']:
        alerts.append("Warning: Poor Air Quality (Fatigue)")
    elif co2 >= t['co2_warn']:
        alerts.append("Notice: Acceptable CO2 (Mild Drowsiness)")

    # 4. Temperature Checks
    if temp > t['temp_max']:
        alerts.append("Warning: Heat Stress Risk")

    # 5. Humidity Checks (Human Comfort/Health)
    if hum > 70.0:
        alerts.append("Warning: High Humidity (Respiratory Risk)")
    elif hum < 30.0:
        alerts.append("Warning: Low Humidity (Dry Air Discomfort)")

    # 6. Sensor Fault Detection
    if o2 > 23.0:
        alerts.append("CRITICAL: O2 Sensor Unstable - Recalibrate")
    if co < -0.5:
        alerts.append("CRITICAL: CO Sensor Baseline Error")
    if o2 < 10.0:
        alerts.append("CRITICAL: Oxygen Sensor Hardware Failure")
    if hum > 99.0:
        alerts.append("Warning: Humidity Sensor Saturation")

    if alerts:
        # Non-blocking: only queue a voice alert if not already speaking
        if speech_queue.empty():
            # If critical levels are hit, speak more urgently
            if "CRITICAL" in "".join(alerts):
                alert_msg = "Danger. Critical levels detected. Escape immediately."
                speech_queue.put(alert_msg)
            else:
                # Use the lowest alert thresholds for hazards
                hazard = "gas" if co > t['co_elevated'] or co2 > t['co2_warn'] else "oxygen"
                speech_queue.put(f"Alert. {hazard} levels unsafe. Check dashboard.")

    return alerts