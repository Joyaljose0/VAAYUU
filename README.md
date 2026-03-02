# VAAYUU: AI-Powered Air Quality Monitoring & Prediction System

VAAYUU is a comprehensive, end-to-end IoT solution designed for real-time air quality monitoring and hazardous condition prediction. Leveraging ESP32 hardware, a Python FastAPI backend with machine learning (LSTM), and a modern React dashboard, it provides life-saving insights through sensors and predictive analytics.

---

## 🚀 How it Works

1.  **Data Collection**: The ESP32 firmware reads data from multiple sensors (CO, CO2, O2, Temperature, Humidity, Pressure). It applies median filtering and calibration algorithms to ensure accuracy.
2.  **Transmission**: Data is transmitted via WiFi (HTTPS/HTTP) or Serial (USB) to the FastAPI backend.
3.  **Processing & Logging**: The backend logs data to CSV files, checks against safety thresholds, and triggers alerts.
4.  **AI Predictions**: 
    -   **LSTM Model**: Predicts future gas concentrations to provide early warning.
    -   **Physiological Model**: Estimates survival/escape time based on oxygen depletion and toxic gas levels.
5.  **Visualization**: A React-based web dashboard displays real-time metrics, historical trends, and predictive alerts with a premium UI.

---

## 📂 Project Structure & File Definitions

### 🔌 Firmware (PlatformIO / ESP32)
Located in `src/`, `include/`, and `lib/`.
-   **`src/main.cpp`**: The core ESP32 logic. Handles sensor initialization (BME280, Oxygen, MQ7, MQ135), OLED display, WiFi Access Point for setup, and data transmission.
-   **`platformio.ini`**: Configuration file for the PlatformIO ecosystem, defining board specs and library dependencies.

### ⚙️ Backend (FastAPI / Python)
Located in `backend/`.
-   **`backend/main.py`**: Entry point for the FastAPI server. Manages API routes and service orchestration.
-   **`backend/api/`**:
    -   `alerts.py`: Logic for calculating hazard levels and triggering visual/system alerts.
-   **`backend/hardware/`**:
    -   `serial_reader.py`: Listens for data incoming via USB serial.
    -   `csv_logger.py`: Appends sensor readings to the local dataset for future model training.
-   **`backend/ml/`**:
    -   `lstm_predict.py`: Core machine learning inference logic for predicting gas trends.
    -   `create_model.py`: Script to define and compile the LSTM neural network architecture.
-   **`backend/requirements.txt`**: Lists all Python dependencies (FastAPI, TensorFlow, Pandas, etc.).
-   **`backend/.env`**: Secret configuration (API keys, ports, etc.).

### 💻 Frontend (React / Vite)
Located in `frontend/`.
-   **`frontend/src/App.tsx`**: Main dashboard component. Orchestrates data fetching and UI state.
-   **`frontend/src/constants.ts`**: Global settings, safety thresholds, and API endpoint configurations.
-   **`frontend/src/types.ts`**: TypeScript definitions for sensor data and API responses.
-   **`frontend/index.html`**: The main entry point for the web application.
-   **`frontend/vite.config.ts`**: Build tool configuration.

### 🤖 Machine Learning & Data
-   **`data/air_quality.csv`**: The dataset containing historical sensor readings used for training.
-   **`scripts/retrain_lstm.py`**: A utility script to retrain the AI models as more data is collected.
-   **`models/`**: Storage for trained model weights (`.h5` or `.pkl` files).

### 🛠️ Automation & Deployment
-   **`run_all.bat`**: One-click Windows script to start the backend, frontend, and serial reader simultaneously.
-   **`stop_all.bat`**: Script to gracefully terminate all running project processes.
-   **`render.yaml`**: Deep configuration for deploying the backend to the Render cloud platform.

---

## 🛠️ Setup & Installation

### 1. Firmware
- Open the root folder in VS Code with the **PlatformIO** extension.
- Connect your ESP32.
- Click **Upload** to flash the firmware.

### 2. Backend
- Navigate to `backend/`.
- Create a virtual environment: `python -m venv .venv`.
- Install dependencies: `pip install -r requirements.txt`.
- Run the server: `uvicorn main:app --reload`.

### 3. Frontend
- Navigate to `frontend/`.
- Install dependencies: `npm install`.
- Start development server: `npm run dev`.

---

## 🛡️ Safety Thresholds
The project uses the following industrial safety standards (configurable in `constants.ts`):
-   **Oxygen**: Alerts at < 19.5% (Deficiency).
-   **CO2**: Alerts at > 5000 ppm (STEL).
-   **CO**: Alerts at > 35 ppm (OSHA PEL).

---

## 📄 License
This project is proprietary and developed for advanced air quality monitoring.
