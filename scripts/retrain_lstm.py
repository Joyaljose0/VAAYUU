import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
import os

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "air_quality.csv")
MODEL_PATH = os.path.join(BASE_DIR, "backend", "ml", "models", "escape_time_lstm.keras")

def generate_escape_times(df):
    """
    Reverse-engineers "Time to Escape" (Y) based on alert conditions.
    If the air is clean, escape time is 60+ mins.
    If an alert triggers, we simulate a countdown based on severity.
    """
    escape_times = []
    
    for i in range(len(df)):
        row = df.iloc[i]
        
        # Safe Baseline
        minutes = 60.0
        
        # Calculate reductions based on toxicity rules
        co = float(row['CO'])
        gas = float(row['Gas'])
        o2 = float(row['Oxygen'])
        temp = float(row['Temp'])
        
        if row['Alert'] != 'no':
            # Severe CO (Deadly within minutes)
            if co > 200: minutes = min(minutes, 5.0)
            elif co > 100: minutes = min(minutes, 15.0)
            elif co > 35: minutes = min(minutes, 45.0)
                
            # Dangerous Gas/Flammables
            if gas > 2000: minutes = min(minutes, 2.0)
            elif gas > 1000: minutes = min(minutes, 10.0)
                
            # Oxygen Asphyxiation
            if o2 < 16.0: minutes = min(minutes, 3.0)
            elif o2 < 19.5: minutes = min(minutes, 20.0)
                
            # Fire / Extreme Heat
            if temp > 50: minutes = min(minutes, 4.0)
            
        # Add a tiny bit of noise so the model doesn't overfit to rigid steps
        noise = np.random.uniform(-0.5, 0.5)
        minutes = max(0.0, min(60.0, minutes + noise))
        escape_times.append(minutes)
        
    return escape_times

def train_model():
    print(f"Loading data from {CSV_PATH}")
    if not os.path.exists(CSV_PATH):
        print("CSV file not found!")
        return
        
    df = pd.read_csv(CSV_PATH)
    
    # We only need the numeric input columns
    # Order must perfectly match backend: [o2, co, gas, temp]
    X_raw = df[['Oxygen', 'CO', 'Gas', 'Temp']].values
    
    # Generate our regression targets (Minutes until critical danger)
    Y = np.array(generate_escape_times(df))
    
    # Min-Max Normalization (Must match lstm_predict.py!)
    mins = np.array([10.0, 0.0, 0.0, -10.0])
    maxs = np.array([25.0, 2000.0, 5000.0, 50.0])
    
    X_norm = np.clip((X_raw - mins) / (maxs - mins), 0.0, 1.0)
    
    # LSTM expects 3D shape: (samples, time_steps, features)
    # We treat each row as an independent 1-step sample for simplicity here
    X_train = X_norm.reshape(X_norm.shape[0], 1, X_norm.shape[1])
    Y_train = Y
    
    print(f"Dataset Shape: X={X_train.shape}, Y={Y_train.shape}")
    
    # Build Model Architecture
    model = Sequential([
        LSTM(32, input_shape=(1, 4), activation='relu', return_sequences=True),
        Dropout(0.2),
        LSTM(16, activation='relu'),
        Dense(8, activation='relu'),
        Dense(1, activation='linear') # Linear output for regression (minutes)
    ])
    
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    
    print("Beginning Training...")
    # Because dataset is small (~1000 rows), we use a high epoch count
    history = model.fit(
        X_train, Y_train, 
        epochs=150, 
        batch_size=16, 
        validation_split=0.1,
        verbose=1
    )
    
    # Save the new model, overwriting the old one
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    model.save(MODEL_PATH)
    print(f"\nModel successfully trained and saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()
