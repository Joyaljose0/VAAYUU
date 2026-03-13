import sys
import os
import pandas as pd
import numpy as np
import tensorflow as tf
import joblib

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from ml.train_from_csv import estimate_escape_time, MODES
from ml.lstm_predict import predict_escape

def evaluate_accuracy(env_mode="BUILDING"):
    config = MODES[env_mode]
    csv_path = config["csv"]
    
    if not os.path.exists(csv_path):
        print(f"No data for {env_mode}")
        return

    # Load data
    df = pd.read_csv(csv_path, names=['co', 'gas', 'temp', 'hum', 'pres', 'oxygen', 'alert', 'legacy_escape'], header=0)
    
    if len(df) < 20:
        print(f"Insufficient data for {env_mode}")
        return

    # Ground Truth
    df['target'] = df.apply(estimate_escape_time, axis=1)
    
    predictions = []
    actuals = []
    
    # We need a rolling window of 10 for prediction
    for i in range(10, len(df)):
        window = df.iloc[i-10:i].to_dict('records')
        # Map keys to what predict_escape expects
        cleaned_window = []
        for d in window:
            cleaned_window.append({
                'co': d['co'],
                'gas': d['gas'],
                'temperature': d['temp'],
                'oxygen': d['oxygen']
            })
            
        pred = predict_escape(cleaned_window, env_mode)
        actual = df.iloc[i]['target']
        
        predictions.append(pred)
        actuals.append(actual)
    
    predictions = np.array(predictions)
    actuals = np.array(actuals)
    
    # Calculation: % Accuracy = 100 - MAPE (Mean Absolute Percentage Error)
    # Since we have 0.5 min as minimum, we won't have div by zero
    mape = np.mean(np.abs((actuals - predictions) / actuals)) * 100
    accuracy = max(0, 100 - mape)
    
    # Precision: Correlation coefficient (how well trends match)
    precision = np.corrcoef(actuals, predictions)[0, 1] * 100
    
    print(f"\n--- Results for {env_mode} ---")
    print(f"Samples Evaluated: {len(predictions)}")
    print(f"Mean Absolute Error: {np.mean(np.abs(actuals - predictions)):.2f} mins")
    print(f"Quantified Accuracy: {accuracy:.2f}%")
    print(f"Trend Precision: {precision:.2f}%")

if __name__ == "__main__":
    evaluate_accuracy("BUILDING")
    evaluate_accuracy("VEHICLE")
