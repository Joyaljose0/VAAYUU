import tensorflow as tf
import numpy as np
import os

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

# ---------------- PHYSIOLOGICAL SURVIVAL ESTIMATION ----------------
def estimate_escape_time(sensor):
    oxygen_time = 60.0
    co_time = 60.0
    co2_time = 60.0
    heat_time = 60.0

    # 🫁 Oxygen Survival (User Physiology Table)
    o2 = sensor["oxygen"]
    if o2 < 10: oxygen_time = 0.5        # 30 sec: Collapse
    elif o2 < 14: oxygen_time = 1.5     # 1.5 min: Fainting
    elif o2 < 17: oxygen_time = 4.0     # 4.0 min: Dizziness
    elif o2 < 19.5: oxygen_time = 12.0  # 12.0 min: Fatigue
    else: oxygen_time = 60.0

    # ☠️ Carbon Monoxide (User Physiology Table)
    co = sensor["co"]
    if co >= 200: co_time = 0.5         # Fatal / Minutes
    elif co >= 50: co_time = 5.0        # Serious poisoning (emergency)
    elif co >= 30: co_time = 60.0       # Dangerous (1-2 hours)
    elif co >= 10: co_time = 240.0      # Unsafe (Headache/Dizziness)
    elif co >= 3: co_time = 480.0       # Elevated
    else: co_time = 600.0

    # 🌫️ Carbon Dioxide (User Physiology Table)
    co2 = sensor["gas"]
    if co2 >= 5000: co2_time = 5.0      # Critical
    elif co2 >= 1500: co2_time = 30.0    # Dangerous
    elif co2 >= 1000: co2_time = 60.0    # Poor Air
    elif co2 >= 800: co2_time = 120.0   # Acceptable
    else: co2_time = 600.0

    # 🌡️ Heat Stress (Standard Safety)
    temp = sensor["temperature"]
    if temp >= 55: heat_time = 5.0
    elif temp >= 45: heat_time = 10.0
    elif temp >= 40: heat_time = 20.0
    else: heat_time = 600.0

    return max(0.5, min(oxygen_time, co_time, co2_time, heat_time))


# ---------------- MAIN PREDICTION ----------------
def predict_escape(sensor):
    try:
        # Input order: [O2, CO, CO2, Temp]
        raw_vals = np.array([
            sensor["oxygen"],
            sensor["co"],
            sensor["gas"],
            sensor["temperature"]
        ])

        X_norm = np.clip((raw_vals - mins) / (maxs - mins), 0.0, 1.0)
        X = X_norm.reshape(1, 1, 4)

        # LSTM prediction
        if model is not None:
            lstm_minutes = float(model.predict(X, verbose=0)[0][0])
            # Max out original prediction to 60.0 (the bounds of training)
            lstm_minutes = max(0.0, min(60.0, lstm_minutes))
        else:
            # Fallback if AI model is missing/corrupt
            lstm_minutes = 60.0

        # Hard bounds using physiological logic
        physio_time = estimate_escape_time(sensor)

        # Final safety-first decision
        escape_time = min(lstm_minutes, physio_time)

        return round(escape_time, 1)

    except Exception as e:
        print(f"LSTM Prediction Error: {e}")
        return 60.0

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