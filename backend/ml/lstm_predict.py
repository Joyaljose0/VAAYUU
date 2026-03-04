import tensorflow as tf
import numpy as np
import os
import time
from collections import deque
from pathlib import Path

# Load model
# We use Pathlib for more robust pathing on Windows/Linux
BASE_DIR = Path(__file__).resolve().parent.parent
model_path = BASE_DIR / "models" / "escape_time_lstm.keras"

model = None
try:
    if model_path.exists():
        model = tf.keras.models.load_model(str(model_path))
        print(f"Successfully loaded LSTM model from {model_path}")
    else:
        print(f"CRITICAL ERROR: Model file not found at {model_path}")
except Exception as e:
    print(f"FAILED TO LOAD MODEL at {model_path}: {e}")

mins = np.array([10.0, 0.0, 0.0, -10.0])
maxs = np.array([25.0, 2000.0, 5000.0, 50.0])

WINDOW_SIZE = 10 # Matches user's sequence_length
MODEL_RELOAD_INTERVAL = 300 # Reload model every 5 minutes or when updated
last_model_load = 0

# Integrity Metrics
accuracy_buffer = deque(maxlen=50) # Compare LSTM vs Physio
precision_buffer = deque(maxlen=50) # Stability of predictions
last_prediction = 60.0

# ---------------- PHYSIOLOGICAL SURVIVAL ESTIMATION ----------------
def estimate_escape_time(sensor):
    oxygen_time = 60.0
    co_time = 60.0
    co2_time = 60.0
    heat_time = 60.0

    # 🫁 Oxygen Survival (Continuous Interpolation)
    # XP: O2 levels, FP: Survival Minutes
    o2_xp = [10.0, 14.0, 17.0, 19.5, 20.9]
    o2_fp = [0.5, 1.5, 4.0, 12.0, 60.0]
    oxygen_time = float(np.interp(sensor["oxygen"], o2_xp, o2_fp))

    # ☠️ Carbon Monoxide (Continuous Interpolation)
    # XP: CO ppm, FP: Survival Minutes
    co_xp = [0.0, 3.0, 10.0, 30.0, 50.0, 200.0]
    co_fp = [600.0, 480.0, 240.0, 60.0, 5.0, 0.5]
    co_time = float(np.interp(sensor["co"], co_xp, co_fp))

    # 🌫️ Carbon Dioxide (Continuous Interpolation)
    # XP: CO2 ppm, FP: Survival Minutes
    co2_xp = [400.0, 800.0, 1000.0, 1500.0, 5000.0]
    co2_fp = [600.0, 120.0, 60.0, 30.0, 5.0]
    co2_time = float(np.interp(sensor["gas"], co2_xp, co2_fp))

    # 🌡️ Heat Stress (Continuous Interpolation)
    # XP: Temp Celsius, FP: Survival Minutes
    temp_xp = [25.0, 40.0, 45.0, 55.0]
    temp_fp = [600.0, 20.0, 10.0, 5.0]
    heat_time = float(np.interp(sensor["temperature"], temp_xp, temp_fp))

    return max(0.5, min(oxygen_time, co_time, co2_time, heat_time))


# ---------------- MAIN PREDICTION ----------------
def predict_escape(sensor_buffer):
    """
    Predicts survival time based on a sequence of sensor data (buffer).
    Matches user's predict_escape_from_sequence logic.
    """
    global model, last_model_load
    try:
        if not sensor_buffer:
            return 60.0

        # Optional: Periodic model reload to pick up background training updates
        current_time = time.time()
        if model is None or (current_time - last_model_load) > MODEL_RELOAD_INTERVAL:
            if model_path.exists():
                model = tf.keras.models.load_model(str(model_path))
                last_model_load = current_time
                print("[AI] Reloaded latest trained model.")

        # Extract features for the entire window
        features = []
        for s in sensor_buffer:
            features.append([
                s["oxygen"],
                s["co"],
                s["gas"], # Maps to user's co2
                s["temperature"]
            ])
        
        # Ensure we have enough data (pad or slice)
        while len(features) < WINDOW_SIZE:
            features.insert(0, features[0])
        features = features[-WINDOW_SIZE:]

        X_raw = np.array(features)
        scaled = np.clip((X_raw - mins) / (maxs - mins), 0.0, 1.0)
        X = scaled.reshape(1, WINDOW_SIZE, 4)

        # LSTM prediction
        if model is not None:
            prediction = float(model.predict(X, verbose=0)[0][0])
            # Maps 0-1 back to 0-60 mins
            lstm_minutes = round(max(0.0, min(60.0, prediction * 60.0)), 1)
        else:
            lstm_minutes = 60.0

        # Hard bounds using physiological logic (on latest frame)
        latest_sensor = sensor_buffer[-1]
        physio_time = estimate_escape_time(latest_sensor)

        # Safety-first: Min of AI trend and Physio logic
        final_time = min(lstm_minutes, physio_time)

        # Update Accuracy Metric: How close is LSTM to Physio limit?
        # A 100% accuracy means LSTM perfectly matches or is more conservative than Physio
        acc = 100.0 - min(100.0, abs(lstm_minutes - physio_time) / 60.0 * 100.0)
        accuracy_buffer.append(acc)

        # Update Precision Metric: Stability of prediction vs last second
        # A 100% precision means zero erratic jumping
        global last_prediction
        prec = 100.0 - min(100.0, abs(final_time - last_prediction) / 60.0 * 100.0)
        precision_buffer.append(prec)
        last_prediction = final_time

        return final_time

    except Exception as e:
        print(f"LSTM Prediction Error: {e}")
        return 60.0

def get_ai_metrics():
    """Returns average accuracy and precision for the dashboard widget."""
    acc = sum(accuracy_buffer) / len(accuracy_buffer) if accuracy_buffer else 100.0
    prec = sum(precision_buffer) / len(precision_buffer) if precision_buffer else 100.0
    return {
        "accuracy": round(acc, 1),
        "precision": round(prec, 1)
    }

# ---------------- ONLINE LEARNING PIPELINE ----------------
def train_on_live_data(sensor_batch):
    """Retrains the LSTM on a batch of live sensor data using Physio labels."""
    if len(sensor_batch) == 0 or model is None:
        return
        
    try:
        X_batch = []
        Y_batch = []
        
        for sensor in sensor_batch:
            raw_vals = np.array([
                sensor["oxygen"],
                sensor["co"],
                sensor["gas"],
                sensor["temperature"]
            ])
            X_norm = np.clip((raw_vals - mins) / (maxs - mins), 0.0, 1.0)
            X_batch.append(X_norm)
            
            # The "Ground Truth" for continuous training is our hardcoded physiological logic
            y_actual = estimate_escape_time(sensor)
            
            # Since the LSTM was historically trained up to 60.0 mins, cap for stable gradients
            y_actual = min(60.0, y_actual)
                
            Y_batch.append(y_actual)
            
        X_tensor = np.array(X_batch).reshape(len(X_batch), 1, 4)
        Y_tensor = np.array(Y_batch)
        
        # Fit the model with a tiny batch of 1 or 2 epochs using live data
        model.fit(X_tensor, Y_tensor, epochs=1, batch_size=len(X_batch), verbose=0)
        
        # Save the updated weights periodically so it learns long-term
        model.save(str(model_path))
        print(f"[ML] Retrained LSTM on {len(X_batch)} live frames and saved weights!")
        
    except Exception as e:
        print(f"Error during Background Model Fit: {e}")