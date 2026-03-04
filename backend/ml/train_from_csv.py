import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from pathlib import Path
import os
import sys
import time

# Add backend root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.lstm_predict import estimate_escape_time, WINDOW_SIZE

# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR.parent / "data" / "air_quality.csv"
MODEL_PATH = BASE_DIR / "models" / "escape_time_lstm.keras"

# Normalization constants
mins = np.array([10.0, 0.0, 0.0, -10.0]) # O2, CO, Gas, Temp
maxs = np.array([25.0, 2000.0, 5000.0, 50.0])

def load_data():
    if not CSV_PATH.exists():
        print(f"Error: CSV not found at {CSV_PATH}")
        return None, None

    df = pd.read_csv(CSV_PATH)
    # Map CSV headers to training requirements
    # CSV: CO,Gas,Temp,Humidity,Pressure,Oxygen,Alert,Escape_Time
    features_raw = df[["Oxygen", "CO", "Gas", "Temp"]].values
    
    # Recalculate labels using the latest physiological logic to ensure high quality training data
    print("Labelling data using physiological safety-first logic...")
    labels = []
    for _, row in df.iterrows():
        sensor = {
            "oxygen": row["Oxygen"],
            "co": row["CO"],
            "gas": row["Gas"],
            "temperature": row["Temp"]
        }
        labels.append(estimate_escape_time(sensor))
    
    labels = np.array(labels) / 60.0 # Normalize 0-60 to 0-1

    # Scale features
    features_scaled = np.clip((features_raw - mins) / (maxs - mins), 0, 1)

    X = []
    y = []

    for i in range(len(features_scaled) - WINDOW_SIZE):
        X.append(features_scaled[i:i+WINDOW_SIZE])
        y.append(labels[i+WINDOW_SIZE])

    return np.array(X), np.array(y)

def build_model():
    model = Sequential([
        LSTM(64, return_sequences=True, input_shape=(WINDOW_SIZE, 4)),
        LSTM(32),
        Dense(16, activation='relu'),
        Dense(1)
    ])

    model.compile(
        optimizer='adam',
        loss='mse',
        metrics=['mae']
    )
    return model

def train_model():
    X, y = load_data()
    if X is None: return

    print(f"Starting training on {len(X)} sequences...")
    model = build_model()

    model.fit(
        X,
        y,
        epochs=3,   # Reduced from 15 to maintain background responsiveness
        batch_size=64, # Increased for speed
        verbose=0 
    )
    # Clear session to free up memory on CPU
    tf.keras.backend.clear_session()

    # Save to a temporary file first then rename to prevent corruption during read/write
    temp_path = str(MODEL_PATH) + ".tmp"
    model.save(temp_path)
    if os.path.exists(str(MODEL_PATH)):
        os.remove(str(MODEL_PATH))
    os.rename(temp_path, str(MODEL_PATH))
    print(f"Model retrained and saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()
