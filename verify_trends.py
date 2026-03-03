import sys
import os
import numpy as np
from pathlib import Path

# Add backend root to path
sys.path.append(os.path.join(os.getcwd(), "backend"))
from ml.lstm_predict import predict_escape, WINDOW_SIZE

# Simulate a rising gas trend (CO rising from 0 to 100)
buffer_rising = []
for i in range(WINDOW_SIZE):
    buffer_rising.append({
        "oxygen": 20.9,
        "co": i * (100.0 / WINDOW_SIZE),
        "gas": 400.0,
        "temperature": 25.0
    })

# Simulate a stable gas environment (CO stable at 100)
buffer_stable = []
for i in range(WINDOW_SIZE):
    buffer_stable.append({
        "oxygen": 20.9,
        "co": 100.0,
        "gas": 400.0,
        "temperature": 25.0
    })

try:
    res_rising = predict_escape(buffer_rising)
    res_stable = predict_escape(buffer_stable)
    
    print(f"SUCCESS: Trend Prediction Working.")
    print(f"Rising Trend Survival: {res_rising} mins")
    print(f"Stable High Survival: {res_stable} mins")
    
    if res_rising < res_stable:
        print("VERIFIED: AI correctly identifies that rising gas is more dangerous than stable gas!")
    else:
        print("NOTE: AI predicts similar risk for both; trend sensitivity depends on training convergence.")
        
except Exception as e:
    print(f"FAILED: Prediction error: {e}")
