import pandas as pd, numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

X, y = [], []
for i in range(100):
    X.append(np.random.rand(1, 4))
    y.append(np.random.randint(1, 10))

X, y = np.array(X), np.array(y)

model = Sequential([
    LSTM(64, input_shape=(1,4)),
    Dense(1)
])
model.compile(optimizer="adam", loss="mse")
model.fit(X, y, epochs=1)

import os
save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", "escape_time_lstm.keras")
model.save(save_path)
print(f"Model saved to {save_path}")
