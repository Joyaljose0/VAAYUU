import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
import os
import joblib

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Config for BOTH modes
MODES = {
    "BUILDING": {
        "csv": os.path.join(PROJECT_ROOT, "data", "air_quality_building.csv"),
        "model": os.path.join(BASE_DIR, "models", "escape_time_lstm_building.keras"),
        "scaler": os.path.join(BASE_DIR, "models", "scaler_building.gz")
    },
    "VEHICLE": {
        "csv": os.path.join(PROJECT_ROOT, "data", "air_quality_vehicle.csv"),
        "model": os.path.join(BASE_DIR, "models", "escape_time_lstm_vehicle.keras"),
        "scaler": os.path.join(BASE_DIR, "models", "scaler_vehicle.gz")
    }
}

def estimate_escape_time(row):
    """Refined physiological ground truth for training labels (Synchronized with alerts.py)."""
    co = row.get('co', 0)
    co2 = row.get('gas', 400)
    o2 = row.get('oxygen', 20.9)
    temp = row.get('temp', 25)

    times = []
    
    # 1. Oxygen (Survival Time in minutes)
    if o2 < 10: times.append(0.5)
    elif o2 < 14: times.append(2)
    elif o2 < 17: times.append(5)
    elif o2 < 19.5: times.append(15)
    else: times.append(60)

    # 2. Carbon Monoxide (Survival Time in minutes)
    # Using thresholds: crit(200), danger(100), unsafe(35), elevated(9)
    if co >= 200: times.append(1)
    elif co >= 100: times.append(5)
    elif co >= 35: times.append(30)
    elif co >= 9: times.append(120)
    else: times.append(600)

    # 3. Carbon Dioxide (Survival Time in minutes)
    # Using thresholds: crit(5000), danger(2500), poor(1000), warn(800)
    if co2 >= 5000: times.append(5)
    elif co2 >= 2500: times.append(15)
    elif co2 >= 1000: times.append(60)
    elif co2 >= 800: times.append(120)
    else: times.append(600)

    # 4. Temperature (Stability in minutes)
    if temp >= 55: times.append(5)
    elif temp >= 45: times.append(15)
    elif temp >= 35: times.append(60)
    else: times.append(600)

    return min(times)

def train_model(env_mode="BUILDING"):
    config = MODES.get(env_mode)
    if not os.path.exists(config["csv"]):
        print(f"[{env_mode}] Skipping: No data at {config['csv']}")
        return

    print(f"[{env_mode}] Loading data for training...")
    df = pd.read_csv(config["csv"], names=['co', 'gas', 'temp', 'hum', 'pres', 'oxygen', 'alert', 'legacy_escape'], header=0)
    
    if len(df) < 50:
        print(f"[{env_mode}] Skipping: Insufficient data ({len(df)} rows)")
        return

    # Calculate target labels using combined physiology
    df['target'] = df.apply(estimate_escape_time, axis=1)

    # Features: CO, Gas, Temp, Oxygen
    features = ['co', 'gas', 'temp', 'oxygen']
    X = df[features].values
    y = df['target'].values

    # Scaling for accuracy
    from sklearn.preprocessing import MinMaxScaler
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Save scaler
    os.makedirs(os.path.dirname(config["scaler"]), exist_ok=True)
    joblib.dump(scaler, config["scaler"])

    # Prepare Sequences (Lookback = 10 steps)
    X_seq, y_seq = [], []
    for i in range(10, len(X_scaled)):
        X_seq.append(X_scaled[i-10:i])
        y_seq.append(y[i])
    
    X_seq, y_seq = np.array(X_seq), np.array(y_seq)

    # Build LSTM Model
    model = Sequential([
        LSTM(64, activation='relu', input_shape=(10, len(features)), return_sequences=True),
        Dropout(0.2),
        LSTM(32, activation='relu'),
        Dense(1) # Predict escape time in minutes
    ])

    model.compile(optimizer='adam', loss='mse')
    
    # OPTIMIZATION: Increased Epochs for Accuracy
    print(f"[{env_mode}] Starting LSTM Training (Accuracy Focus)...")
    model.fit(X_seq, y_seq, epochs=20, batch_size=16, verbose=0)
    
    model.save(config["model"])
    print(f"[{env_mode}] Model and Scaler Saved Successfully.")

if __name__ == "__main__":
    for m in MODES:
        train_model(m)
