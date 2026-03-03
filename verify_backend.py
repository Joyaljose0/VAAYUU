import sys
import os
from pathlib import Path

# Add backend to path for verification
backend_path = os.path.join(os.getcwd(), "backend")
sys.path.append(backend_path)

try:
    from ml.lstm_predict import predict_escape
    print("SUCCESS: Imports working correctly.")
except Exception as e:
    print(f"FAILED: Import error: {e}")

# Test dummy prediction
dummy_sensor = {
    "oxygen": 20.9,
    "co": 0.5,
    "gas": 400.0,
    "temperature": 25.0
}

try:
    res = predict_escape(dummy_sensor)
    print(f"SUCCESS: Prediction working. Escape time: {res}")
except Exception as e:
    print(f"FAILED: Prediction error: {e}")
