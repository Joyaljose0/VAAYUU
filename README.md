# 🌬️ VAAYUU: Next-Gen AI Air Quality Sentinel

> **Safeguarding Lives Through Real-Time IoT Monitoring & Predictive AI.**

VAAYUU is a high-performance ecosystem integrating **ESP32 hardware**, **FastAPI microservices**, and **Machine Learning** to detect hazardous gases before they become life-threatening. With advanced LSTM trend prediction and physiological survival modeling, VAAYUU isn't just a sensor—it's a clinical-grade atmospheric intelligence system.

---

## ✨ Key Features
-   🛰️ **Multi-Sensor Fusion**: Real-time tracking of O2, CO2, CO, Temp, Humidity, and Pressure.
-   🧠 **Predictive Intelligence**: LSTM-based modeling to forecast gas concentration trends.
-   ⏱️ **Survival Modeling**: Estimates "Time-to-Escape" based on physiological oxygen depletion.
-   📱 **Premium Dashboard**: A sleek, reactive UI for instant hazard visualization.
-   ☁️ **Cloud Ready**: Built-in support for Render deployment and HTTPS security.

---

## 🏗️ Project Architecture & Structure

VAAYUU is split into three core pillars: **Firmware**, **Intelligence (Backend)**, and **Experience (Frontend)**.

### 📂 File Structure Overview
```text
VAAYUU/
├── 🔌 src/                 # ESP32 Firmware (C++)
│   └── main.cpp            # Core logic, sensor fusion, & WiFi Setup
├── ⚙️ backend/             # Intelligence Layer (Python/FastAPI)
│   ├── api/                # REST Routes & Alert Logic
│   │   ├── main.py         # FastAPI Entry Point
│   │   └── alerts.py       # Hazard analysis algorithms
│   ├── hardware/           # IO Interfaces
│   │   ├── serial_reader.py# USB-Serial data bridge
│   │   └── csv_logger.py   # Dataset acquisition
│   ├── ml/                 # AI Engine
│   │   ├── lstm_predict.py # Live trend inference
│   │   └── create_model.py # Neural network definition
│   └── requirements.txt    # Python dependencies
├── 💻 frontend/            # Dashboard (React/Vite/TS)
│   ├── src/                # UI Components & Services
│   │   ├── App.tsx         # Dashboard Orchestrator
│   │   └── constants.ts    # Global Safety Thresholds
│   └── vite.config.ts      # Build pipeline
├── 🤖 models/              # Trained AI Models (.h5)
├── 📊 data/                # Air quality datasets (.csv)
├── 🛠️ scripts/             # Retraining & automation utilities
├── 🚀 run_all.bat          # One-click system startup
└── 📄 render.yaml          # Cloud deployment manifest
```

---

## 🛠️ Step-by-Step Setup

### 1️⃣ Firmware Initialization (ESP32)
*Required: VS Code + [PlatformIO Extension]*
1.  Connect your ESP32 via USB.
2.  Open the root `VAAYUU` folder in VS Code.
3.  Click the **PlatformIO: Build** icon, then **Upload**.
4.  *(Optional)* Hold the digital pin assigned to MQ7 during boot to force WiFi Setup mode.

### 2️⃣ Intelligence Layer (Backend)
*Required: Python 3.9+*
1.  `cd backend`
2.  `python -m venv .venv`
3.  `source .venv/bin/activate` (or `.venv\Scripts\activate` on Windows)
4.  `pip install -r requirements.txt`
5.  `uvicorn main:app --reload --port 8000`

### 3️⃣ Experience Layer (Frontend)
*Required: Node.js 16+*
1.  `cd frontend`
2.  `npm install`
3.  `npm run dev`
4.  Open [http://localhost:5173](http://localhost:5173) in your browser.

> [!TIP]
> Use **`run_all.bat`** in the root directory to launch the entire stack (Backend + Frontend + Serial Bridge) with a single double-click!

---

## � Safety Standards
The system operates based on international safety thresholds:
-   **Oxygen (O2)**: 🚩 Critical < 19.5%
-   **Carbon Monoxide (CO)**: ⚠️ Warning > 35 ppm
-   **Carbon Dioxide (CO2)**: ⚠️ Warning > 5000 ppm

---

## 🤝 Project Origin
This project is developed as a sophisticated solution for industrial and domestic air safety monitoring.

---
*Created by VAAYUU Team.*
