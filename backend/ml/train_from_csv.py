import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
import os
import joblib

# Config for BOTH modes
MODES = {
    "BUILDING": {
        "csv": "data/air_quality_building.csv",
        "model": "backend/models/escape_time_lstm_building.keras",
        "scaler": "backend/models/scaler_building.gz"
    },
    "VEHICLE": {
        "csv": "data/air_quality_vehicle.csv",
        "model": "backend/models/escape_time_lstm_vehicle.keras",
        "scaler": "backend/models/scaler_vehicle.gz"
    }
}

def estimate_escape_time(row):
    """Refined physiological ground truth for training labels."""
    co = row.get('co', 0)
    co2 = row.get('gas', 400) # Using 'gas' as CO2 proxy if not explicitly labeled
    o2 = row.get('oxygen', 20.9)
    temp = row.get('temp', 25)

    times = []
    
    # O2 survival (User provided thresholds)
    if o2 < 10: times.append(0.5)
    elif o2 < 14: times.append(1.5)
    elif o2 < 17: times.append(4)
    elif o2 < 19.5: times.append(12)
    else: times.append(60)

    # CO survival
    if co >= 200: times.append(0.5)
    elif co >= 50: times.append(5)
    elif co >= 30: times.append(60)
    elif co >= 10: times.append(240)
    else: times.append(600)

    # CO2 survival (Proxy)
    if co2 >= 5000: times.append(5)
    elif co2 >= 1500: times.append(30)
    elif co2 >= 1000: times.append(60)
    else: times.append(600)

    # Heat survival
    if temp >= 55: times.append(5)
    elif temp >= 45: times.append(10)
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
    os.makedirs("backend/models", exist_ok=True)
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
