/// <reference types="vite/client" />
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Wind,
  Activity,
  AlertTriangle,
  ShieldCheck,
  TrendingUp,
  Building2,
  Car,
  Bell,
  Settings,
  BrainCircuit,
  Zap,
  Volume2,
  VolumeX,
  Clock,
  Wifi,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';
import { SensorData, EnvironmentType, Alert } from './types';
import {
  BUILDING_THRESHOLDS,
  VEHICLE_THRESHOLDS,
  SENSOR_CONFIG,
  CO2_STATUS,
  CO_STATUS,
  O2_STATUS
} from './constants';

// --- Live Fetching Logic ---
const getBackendUrl = (source: 'RENDER' | 'LOCAL') => {
  if (source === 'LOCAL') return `http://${window.location.hostname}:8000`;
  return import.meta.env.VITE_BACKEND_URL || `https://vaayuu-backend.onrender.com`;
};

const fetchLiveReading = async (source: 'RENDER' | 'LOCAL'): Promise<{ data: SensorData | null, status: 'ok' | 'offline' | 'waiting' }> => {
  try {
    const backendUrl = getBackendUrl(source);

    const response = await fetch(`${backendUrl}/live?t=${Date.now()}`, {
      cache: 'no-store',
      headers: {
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache'
      }
    });

    if (!response.ok) {
      console.error(`Backend returned ${response.status}`);
      return { data: null, status: 'offline' };
    }

    const data = await response.json();

    // If the server is up but hasn't received any hardware data yet
    if (!data || typeof data !== 'object' || !('temperature' in data)) {
      return { data: null, status: 'waiting' };
    }

    const extract = (val: any): number => {
      if (val === undefined || val === null) return 0;
      return Number(val) || 0;
    };

    const reading = {
      timestamp: Date.now(),
      temperature: extract(data.temperature),
      pressure: extract(data.pressure),
      humidity: extract(data.humidity),
      co2: extract(data.gas),
      co: extract(data.co),
      o2: extract(data.oxygen),
      last_updated: data.last_updated || 0,
      is_warming_up: !!data.is_warming_up,
      env_mode: data.env_mode as EnvironmentType
    } as SensorData;

    return { data: reading, status: 'ok' };
  } catch (err) {
    console.error("Backend unreachable:", err);
    return { data: null, status: 'offline' };
  }
};

const App: React.FC = () => {
  const [env, setEnv] = useState<EnvironmentType>('BUILDING');
  const [currentTime, setCurrentTime] = useState(new Date());
  const [history, setHistory] = useState<SensorData[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isCritical, setIsCritical] = useState(false);
  const [buzzerEnabled, setBuzzerEnabled] = useState(true);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // AI Countdown states
  const [predictionAnchor, setPredictionAnchor] = useState<{ timeMs: number, escapeSeconds: number } | null>(null);
  const [countdownSeconds, setCountdownSeconds] = useState<number | null>(null);
  const [physioAnchor, setPhysioAnchor] = useState<{ timeMs: number, escapeSeconds: number } | null>(null);
  const [physioSeconds, setPhysioSeconds] = useState<number | null>(null);

  // WiFi Config States
  const [showWifiConfig, setShowWifiConfig] = useState(false);
  const [wifiSsid, setWifiSsid] = useState('');
  const [wifiPassword, setWifiPassword] = useState('');
  const [wifiIp, setWifiIp] = useState(window.location.hostname === 'localhost' ? '' : window.location.hostname);
  const [wifiStatus, setWifiStatus] = useState<string | null>(null);

  const [connectionMode, setConnectionMode] = useState<string>('USB');
  const [backendSource, setBackendSource] = useState<'RENDER' | 'LOCAL'>(() => {
    return (localStorage.getItem('vaayuu-backend-source') as 'RENDER' | 'LOCAL') || 'RENDER';
  });

  useEffect(() => {
    localStorage.setItem('vaayuu-backend-source', backendSource);
  }, [backendSource]);

  const audioCtxRef = useRef<AudioContext | null>(null);
  const buzzerIntervalRef = useRef<number | null>(null);

  const currentData = history[history.length - 1];

  const activeThresholds = env === 'BUILDING' ? BUILDING_THRESHOLDS : VEHICLE_THRESHOLDS;
  const thresholdsRef = useRef(activeThresholds);

  // Keep the ref synced for the interval loop
  useEffect(() => {
    thresholdsRef.current = activeThresholds;
  }, [activeThresholds]);

  // If accessed via localhost, auto-fill the real LAN IP from the backend once we receive it
  useEffect(() => {
    if (currentData?.backend_ip && wifiIp === '') {
      setWifiIp(currentData.backend_ip);
    }
  }, [currentData?.backend_ip, wifiIp]);

  const currentRemaining = Math.min(countdownSeconds ?? 3600, physioSeconds ?? 3600);

  // Automatically sync local UI mode from backend state
  useEffect(() => {
    if (currentData?.env_mode && currentData.env_mode !== env) {
      console.log(`[Sync] Local UI mode updated from backend: ${currentData.env_mode}`);
      setEnv(currentData.env_mode);
    }
  }, [currentData?.env_mode, env]);

  // Update current time and calculate live countdown
  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      setCurrentTime(new Date(now));

      setPredictionAnchor(anchor => {
        if (!anchor) {
          setCountdownSeconds(null);
          return null;
        }
        const secondsElapsed = Math.floor((now - anchor.timeMs) / 1000);
        const remaining = Math.max(0, anchor.escapeSeconds - secondsElapsed);
        setCountdownSeconds(remaining);
        return anchor;
      });

      setPhysioAnchor(anchor => {
        if (!anchor) {
          setPhysioSeconds(null);
          return null;
        }
        const secondsElapsed = Math.floor((now - anchor.timeMs) / 1000);
        const remaining = Math.max(0, anchor.escapeSeconds - secondsElapsed);
        setPhysioSeconds(remaining);
        return anchor;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Buzzer Audio Logic
  const triggerBuzzer = useCallback(() => {
    if (!buzzerEnabled) return;
    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }

    const ctx = audioCtxRef.current;
    if (ctx.state === 'suspended') ctx.resume();

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'square';
    osc.frequency.setValueAtTime(1200, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.1);

    gain.gain.setValueAtTime(0.1, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.15);
  }, [buzzerEnabled]);

  // Handle Critical Alert State Effects
  useEffect(() => {
    if (isCritical) {
      // Start buzzer interval
      if (!buzzerIntervalRef.current) {
        buzzerIntervalRef.current = window.setInterval(() => {
          triggerBuzzer();
          if ('vibrate' in navigator) {
            navigator.vibrate([300, 100, 300]);
          }
        }, 500);
      }
    } else {
      if (buzzerIntervalRef.current) {
        clearInterval(buzzerIntervalRef.current);
        buzzerIntervalRef.current = null;
      }
    }
    return () => {
      if (buzzerIntervalRef.current) clearInterval(buzzerIntervalRef.current);
    };
  }, [isCritical, triggerBuzzer]);

  // ---------------- ESCAPE TIME ESTIMATION (FRONTEND SAFE MODEL) ----------------
  const estimateEscapeTime = useCallback((data: SensorData): number => {
    if (!data) return 60;
    let oxygenTime = 60;
    let coTime = 60;
    let co2Time = 60;
    let heatTime = 60;

    if (data.o2 < 10) oxygenTime = 0.5;
    else if (data.o2 < 14) oxygenTime = 1.5;
    else if (data.o2 < 17) oxygenTime = 4;
    else if (data.o2 < 19.5) oxygenTime = 12;

    if (data.co >= 200) coTime = 0.5;
    else if (data.co >= 50) coTime = 5;
    else if (data.co >= 30) coTime = 60;
    else if (data.co >= 10) coTime = 240;

    if (data.co2 >= 5000) co2Time = 5;
    else if (data.co2 >= 1500) co2Time = 30;
    else if (data.co2 >= 1000) co2Time = 60;

    if (data.temperature >= 55) heatTime = 5;
    else if (data.temperature >= 45) heatTime = 10;

    return Math.max(0.5, Math.min(oxygenTime, coTime, co2Time, heatTime));
  }, []);

  // Initialize and update readings
  useEffect(() => {
    let mounted = true;

    const interval = setInterval(async () => {
      const { data: newData, status } = await fetchLiveReading(backendSource);

      if (!mounted) return;

      if (status === 'offline') {
        const backendUrl = getBackendUrl(backendSource);
        setConnectionError(`Backend Offline: Cannot reach ${backendUrl}. Please check Render status.`);
        return;
      }

      if (status === 'waiting') {
        setConnectionError("Backend Online: Waiting for first hardware data packet from ESP32...");
        return;
      }

      // If we got here, status is 'ok'
      if (!newData) return;

      const nowSecs = Math.floor(Date.now() / 1000);
      // @ts-ignore
      if (newData.last_updated > 0 && (nowSecs - newData.last_updated > 10)) {
        // @ts-ignore
        setConnectionError(`Hardware Link Lost: No new data from ESP32 in 10s. Check device WiFi.`);
        return;
      }

      setConnectionError(null);

      // Use type assertion for backend-specific fields not in base SensorData
      const extendedData = newData as any;
      setConnectionMode(prev => extendedData.connection_mode || prev);

      // Inline alert checking to avoid stale closures.
      // We pull the LIVE values from thresholdsRef, which is updated whenever env changes!
      let criticalDetected = false;
      const newAlerts: Alert[] = [];
      const currentThresholds = thresholdsRef.current;

      if (newData.co2 > currentThresholds.co2) {
        const co2Level = CO2_STATUS.find(s => newData.co2 >= s.min && newData.co2 <= s.max);
        newAlerts.push({
          id: Math.random().toString(),
          type: newData.co2 > currentThresholds.co2 * 1.5 ? 'DANGER' : 'WARNING',
          sensor: 'co2',
          message: co2Level ? `${co2Level.status}: ${co2Level.desc}. PRECAUTION: ${co2Level.precaution}` : 'High CO2 level detected.',
          timestamp: Date.now(),
          value: newData.co2
        });
        if (newData.co2 > currentThresholds.co2 * 1.5) criticalDetected = true;
      }

      if (newData.co > currentThresholds.co) {
        const coLevel = CO_STATUS.find(s => newData.co >= s.min && newData.co <= s.max);
        newAlerts.push({
          id: Math.random().toString(),
          type: newData.co > currentThresholds.co * 3 ? 'DANGER' : 'WARNING',
          sensor: 'co',
          message: coLevel ? `${coLevel.status}: ${coLevel.desc}. PRECAUTION: ${coLevel.precaution}` : 'Elevated CO level detected.',
          timestamp: Date.now(),
          value: newData.co
        });
        if (newData.co > currentThresholds.co * 3) criticalDetected = true;
      }

      if (newData.o2 < currentThresholds.o2Min) {
        const o2Level = O2_STATUS.find(s => newData.o2 >= s.min && newData.o2 <= s.max);
        newAlerts.push({
          id: Math.random().toString(),
          type: newData.o2 < 17 ? 'DANGER' : 'WARNING',
          sensor: 'o2',
          message: o2Level ? `${o2Level.status}: Time Remaining approx ${o2Level.time}. PRECAUTION: ${o2Level.precaution}` : 'Low Oxygen detected.',
          timestamp: Date.now(),
          value: newData.o2
        });
        if (newData.o2 < 17) criticalDetected = true;
      }

      // Merge frontend and backend alerts
      const backendAlerts: Alert[] = (newData as any).backend_alerts?.map((msg: string) => ({
        id: `backend-${Math.random()}`,
        type: msg.startsWith('CRITICAL') ? 'DANGER' : 'WARNING',
        sensor: msg.toLowerCase().includes('oxygen') ? 'o2' : (msg.toLowerCase().includes('co2') ? 'co2' : 'co'),
        message: msg,
        timestamp: Date.now(),
        value: 0
      })) || [];

      setIsCritical(criticalDetected || backendAlerts.some(a => a.type === 'DANGER'));

      const allNewAlerts = [...newAlerts, ...backendAlerts];
      if (allNewAlerts.length > 0) {
        setAlerts(prev => {
          // Filter out duplicates (simple message check)
          const existingMsgs = new Set(prev.map(a => a.message));
          const uniqueNew = allNewAlerts.filter(a => !existingMsgs.has(a.message));
          return [...uniqueNew, ...prev].slice(0, 20);
        });
      }

      // Important: Force a new array reference
      setHistory(prev => {
        const arr = [...prev, { ...newData }];
        if (arr.length > 50) return arr.slice(arr.length - 50);
        return arr;
      });

      // Update AI Prediction
      if (newData.escape_time !== undefined && newData.escape_time !== null) {
        const newSeconds = Math.floor(newData.escape_time * 60);
        setPredictionAnchor(prev => {
          if (!prev || Math.abs(prev.escapeSeconds - newSeconds) > 10) {
            return { timeMs: Date.now(), escapeSeconds: newSeconds };
          }
          return prev;
        });
      } else {
        setPredictionAnchor(null);
        setCountdownSeconds(null);
      }

      // Update Physio countdown
      const physioEst = estimateEscapeTime(newData);
      if (physioEst !== null) {
        const newSeconds = Math.floor(physioEst * 60);
        setPhysioAnchor(prev => {
          if (!prev || Math.abs(prev.escapeSeconds - newSeconds) > 30) {
            return { timeMs: Date.now(), escapeSeconds: newSeconds };
          }
          return prev;
        });
      }

      // History update

    }, 1000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []); // Empty dependency array is fine since we use refs


  const handleWifiConnect = async () => {
    setWifiStatus("Sending...");
    const backendUrl = getBackendUrl(backendSource);
    try {
      const res = await fetch(`${backendUrl}/config-wifi`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ssid: wifiSsid, password: wifiPassword, ip: wifiIp })
      });
      if (res.ok) {
        setWifiStatus("Configuration sent");
        setTimeout(() => setShowWifiConfig(false), 2000);
      } else {
        setWifiStatus("Failed to send");
      }
    } catch (e) {
      setWifiStatus("Network error");
    }
  };

  if (!currentData || currentData.is_warming_up) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-slate-950 text-white space-y-6">
        <div className="relative">
          <div className="animate-spin rounded-full h-20 w-20 border-t-2 border-b-2 border-indigo-500/50"></div>
          {currentData?.is_warming_up && (
            <div className="absolute inset-0 flex items-center justify-center animate-pulse">
              <span className="text-[10px] font-black text-indigo-400 uppercase tracking-tighter">Warming</span>
            </div>
          )}
        </div>

        <div className="text-center space-y-2">
          <p className="text-2xl font-bold tracking-tight">
            {currentData?.is_warming_up ? "Sensors Stabilizing..." : "Initializing System..."}
          </p>
          <div className="flex items-center justify-center gap-2">
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${backendSource === 'RENDER' ? 'bg-indigo-500/20 text-indigo-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
              Source: {backendSource}
            </span>
            <span className="text-slate-600 text-[10px]">•</span>
            <span className="text-slate-500 text-[10px] uppercase font-bold tracking-widest leading-none">
              AuraGuard v2.2
            </span>
          </div>
        </div>

        <div className="text-slate-400 text-sm max-w-sm text-center leading-relaxed">
          {currentData?.is_warming_up
            ? "Your hardware is connected! Chemical sensors require dynamic thermal stabilization to reach baseline accuracy."
            : "Waiting for backend handshake. Verify that your hardware is streaming and the backend is responsive."}
        </div>

        {currentData?.is_warming_up && (
          <div className="flex flex-col items-center gap-2">
            <div className="h-1 w-48 bg-slate-900 rounded-full overflow-hidden">
              <div className="h-full bg-indigo-500 animate-loading-bar" />
            </div>
            <p className="text-[10px] text-indigo-400/60 uppercase tracking-widest animate-pulse font-bold">
              Estimated wait: ~2 minutes
            </p>
          </div>
        )}

        {connectionError && (
          <div className="glass mt-8 p-5 border border-red-500/20 bg-red-500/5 rounded-2xl max-w-sm">
            <p className="text-[10px] font-black uppercase text-red-500 mb-2 tracking-widest flex items-center gap-2">
              <AlertCircle className="w-3 h-3" /> Connection Status
            </p>
            <p className="text-xs text-red-100/60 font-medium leading-relaxed">{connectionError}</p>
          </div>
        )}

        {!currentData?.is_warming_up && !connectionError && (
          <p className="text-[10px] text-slate-700 italic">
            Connecting to {backendSource === 'RENDER' ? 'Cloud' : 'Local'} API...
          </p>
        )}
      </div>
    );
  }

  // Debug log to ensure rendering is happening with new data
  console.log("App Rendering with currentData:", currentData);

  // ---------------- ESCAPE TIME ESTIMATION (FRONTEND SAFE MODEL) ----------------
  // [MOVED UP TO AVOID REACT HOISTING CLOSURE BUGS]

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 overflow-hidden">
      {/* Alert Strobe Layer */}
      {isCritical && <div className="animate-strobe" />}

      {/* Sensor Warmup Overlay */}
      {currentData?.is_warming_up && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-6">
          <div className="bg-slate-800 p-8 rounded-2xl border border-blue-500/30 shadow-2xl max-w-sm w-full text-center space-y-4">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin mx-auto"></div>
              <Activity className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-blue-400 w-6 h-6 animate-pulse" />
            </div>
            <h2 className="text-xl font-bold text-white">Sensor Warming Up</h2>
            <p className="text-slate-400 text-sm">
              Stabilizing chemical baselines. This takes about 2 minutes to ensure precision readings.
            </p>
            <div className="flex justify-center gap-1">
              {[0, 1, 2].map((i) => (
                <div key={i} className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.2}s` }}></div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="sticky top-0 z-50 glass border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg shadow-lg transition-colors ${isCritical ? 'bg-red-600 shadow-red-500/50 animate-pulse' : 'bg-indigo-600 shadow-indigo-500/20'}`}>
            <Wind className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
              VAAYUU
            </h1>
            <p className="text-xs text-slate-500 font-medium uppercase tracking-widest">
              smart monitoring system
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Time Widget */}
          <div className="hidden sm:flex items-center gap-2 px-4 py-1.5 rounded-full bg-slate-900/50 border border-slate-800 text-sm font-medium text-slate-300 shadow-inner">
            <Clock className="w-4 h-4 text-indigo-400" />
            {currentTime.toLocaleTimeString()}
          </div>

          {/* Backend Switcher */}
          <div className="flex bg-slate-900/50 p-1 rounded-full border border-slate-800 gap-1 scale-90 sm:scale-100">
            <button
              onClick={() => setBackendSource('RENDER')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase transition-all ${backendSource === 'RENDER' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}
              title="Connect to Cloud (Render)"
            >
              Cloud
            </button>
            <button
              onClick={() => setBackendSource('LOCAL')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase transition-all ${backendSource === 'LOCAL' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}
              title="Connect to Localhost:8000"
            >
              Local
            </button>
          </div>

          {/* Settings / Calibration */}
          <div className="flex bg-slate-900/50 p-1 rounded-full border border-slate-800 gap-1">
            <button
              onClick={async () => {
                if (window.confirm("Perform FULL SYSTEM CALIBRATION? Ensure EVERYTHING is in CLEAN FRESH AIR.")) {
                  try {
                    const backendUrl = getBackendUrl(backendSource);
                    await fetch(`${backendUrl}/command`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ command: "CAL_ALL" })
                    });
                    alert("Full System Calibration command sent.");
                  } catch (e) { alert("Failed to send command."); }
                }
              }}
              className="p-1 px-3 text-[9px] font-bold uppercase text-white bg-indigo-600/50 hover:bg-indigo-600 rounded-l-full border-r border-slate-800"
              title="Calibrate All Sensors to Baseline"
            >
              Calibrate All
            </button>
            <button
              onClick={async () => {
                if (window.confirm("Trigger Oxygen Calibration? Ensure device is in FRESH AIR (20.9%).")) {
                  try {
                    const backendUrl = getBackendUrl(backendSource);
                    await fetch(`${backendUrl}/command`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ command: "CAL_O2" })
                    });
                    alert("O2 Calibration command sent.");
                  } catch (e) { alert("Failed to send command."); }
                }
              }}
              className="p-1 px-2 text-[9px] font-bold uppercase text-blue-400 hover:text-blue-300 border-r border-slate-800"
              title="Calibrate O2 only"
            >
              O2
            </button>
            <button
              onClick={async () => {
                if (window.confirm("Zero MQ7 (CO)? Ensure device is in CLEAN AIR.")) {
                  try {
                    const backendUrl = getBackendUrl(backendSource);
                    await fetch(`${backendUrl}/command`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ command: "CAL_CO7" })
                    });
                    alert("CO Calibration command sent.");
                  } catch (e) { alert("Failed to send command."); }
                }
              }}
              className="p-1 px-2 text-[9px] font-bold uppercase text-orange-400 hover:text-orange-300 border-r border-slate-800"
              title="Zero CO only"
            >
              CO
            </button>
            <button
              onClick={async () => {
                if (window.confirm("Zero MQ135 (CO2)? Ensure device is in CLEAN AIR.")) {
                  try {
                    const backendUrl = getBackendUrl(backendSource);
                    await fetch(`${backendUrl}/command`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ command: "CAL_CO2" })
                    });
                    alert("CO2 Calibration command sent.");
                  } catch (e) { alert("Failed to send command."); }
                }
              }}
              className="p-1 px-2 text-[9px] font-bold uppercase text-emerald-400 hover:text-emerald-300 rounded-r-full"
              title="Zero CO2 only"
            >
              CO2
            </button>
          </div>

          <div className="flex bg-slate-900/50 p-1 rounded-full border border-slate-800 relative">
            <button
              onClick={async () => {
                if (env === 'BUILDING') return;
                setEnv('BUILDING');
                const backendUrl = getBackendUrl(backendSource);
                const localUrl = `http://${window.location.hostname}:8000`;
                try {
                  // Sync mode to BOTH local machine (for USB logging) and current active backend
                  fetch(`${localUrl}/env-mode`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'BUILDING' }) }).catch(e=>console.error(e));
                  await fetch(`${backendUrl}/env-mode`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'BUILDING' }) });
                  
                  await fetch(`${backendUrl}/train`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'BUILDING' }) });
                  
                  // Keep local backend trained as well if testing locally
                  if (backendUrl !== localUrl) {
                      fetch(`${localUrl}/train`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'BUILDING' }) }).catch(e=>console.error(e));
                  }
                  alert("Switched to Building. Training started.");
                } catch (e) { console.error("Failed to switch and train BUILDING", e); }
              }}
              className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium transition-all ${env === 'BUILDING' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}
            >
              <Building2 className="w-4 h-4" /> Building
            </button>
            <button
              onClick={async () => {
                if (env === 'VEHICLE') return;
                setEnv('VEHICLE');
                const backendUrl = getBackendUrl(backendSource);
                const localUrl = `http://${window.location.hostname}:8000`;
                try {
                  // Sync mode to BOTH local machine (for USB logging) and current active backend
                  fetch(`${localUrl}/env-mode`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'VEHICLE' }) }).catch(e=>console.error(e));
                  await fetch(`${backendUrl}/env-mode`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'VEHICLE' }) });
                  
                  await fetch(`${backendUrl}/train`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'VEHICLE' }) });
                  
                  // Keep local backend trained as well if testing locally
                  if (backendUrl !== localUrl) {
                      fetch(`${localUrl}/train`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'VEHICLE' }) }).catch(e=>console.error(e));
                  }
                  alert("Switched to Vehicle. Training started.");
                } catch (e) { console.error("Failed to switch and train VEHICLE", e); }
              }}
              className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium transition-all ${env === 'VEHICLE' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}
            >
              <Car className="w-4 h-4" /> Vehicle
            </button>
          </div>

          {/* Connection Mode Toggle */}
          <button
            onClick={async () => {
              const newMode = connectionMode === 'USB' ? 'WIFI' : 'USB';
              const backendUrl = import.meta.env.VITE_BACKEND_URL || `http://${window.location.hostname}:8000`;
              try {
                const res = await fetch(`${backendUrl}/connection-mode`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ mode: newMode })
                });
                if (res.ok) setConnectionMode(newMode);
              } catch (e) { console.error("Failed to switch mode"); }
            }}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all text-sm font-bold ${connectionMode === 'WIFI'
              ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20'
              : 'text-indigo-400 border-indigo-500/30 bg-indigo-500/10 hover:bg-indigo-500/20'
              }`}
            title={`Current Mode: ${connectionMode}. Click to switch.`}
          >
            {connectionMode === 'WIFI' ? <Wifi className="w-4 h-4" /> : <Activity className="w-4 h-4" />}
            {connectionMode}
          </button>

          {/* WiFi Config Toggle */}
          <button
            onClick={() => setShowWifiConfig(!showWifiConfig)}
            className={`p-2 rounded-lg border transition-all ${showWifiConfig ? 'text-indigo-400 border-indigo-500/20 bg-indigo-500/5' : 'text-slate-500 border-slate-800 bg-slate-900'}`}
            title="Configure WiFi"
          >
            <Wifi className="w-5 h-5" />
          </button>

          {/* Buzzer Toggle */}
          <button
            onClick={() => setBuzzerEnabled(!buzzerEnabled)}
            className={`p-2 rounded-lg border transition-all ${buzzerEnabled ? 'text-indigo-400 border-indigo-500/20 bg-indigo-500/5' : 'text-slate-500 border-slate-800 bg-slate-900'}`}
            title={buzzerEnabled ? "Buzzer On" : "Buzzer Muted"}
          >
            {buzzerEnabled ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
          </button>

          <button className="p-2 text-slate-400 hover:text-white transition-colors relative">
            <Bell className="w-5 h-5" />
            {alerts.length > 0 && <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full animate-ping" />}
          </button>
        </div>
      </header>

      {/* WiFi Config Modal */}
      {
        showWifiConfig && (
          <div className="absolute top-20 right-6 z-50 glass border border-slate-800 p-4 rounded-xl shadow-2xl w-72">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2 text-slate-200">
              <Wifi className="w-4 h-4 text-indigo-400" />
              ESP32 WiFi Config
            </h3>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="SSID"
                value={wifiSsid}
                onChange={e => setWifiSsid(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500"
              />
              <input
                type="password"
                placeholder="Password"
                value={wifiPassword}
                onChange={e => setWifiPassword(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500"
              />
              <input
                type="text"
                placeholder="Backend IP (e.g., 192.168.1.5)"
                value={wifiIp}
                onChange={e => setWifiIp(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500"
              />
              <button
                onClick={handleWifiConnect}
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white rounded-md py-2 text-sm font-medium transition-colors"
              >
                Connect
              </button>
              {wifiStatus && (
                <p className="text-xs text-center text-slate-400 mt-2">{wifiStatus}</p>
              )}
            </div>
          </div>
        )
      }

      {/* Hazard Banner */}
      {
        (isCritical || alerts.some(a => a.message.includes("Humidity") || a.message.includes("Heat"))) && (
          <div className={`text-white px-6 py-2 flex items-center justify-center gap-3 animate-pulse shadow-xl relative z-40 ${isCritical ? 'bg-red-600' : 'bg-orange-500'}`}>
            <AlertTriangle className="w-5 h-5" />
            <span className="font-bold text-sm tracking-widest uppercase">
              {isCritical ? "Emergency Protocol: Ventilate Now" : "Environmental Health Alert: Check Dashboard"}
            </span>
          </div>
        )
      }

      {/* Disconnection Banner */}
      {
        connectionError && (
          <div className="bg-orange-600/90 text-white px-6 py-3 flex items-center justify-center gap-3 shadow-[0_4px_20px_rgba(234,88,12,0.5)] border-b border-orange-400 relative z-40">
            <Wifi className="w-5 h-5 animate-pulse" />
            <span className="font-bold text-sm tracking-wide">{connectionError}</span>
          </div>
        )
      }

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

          {/* Main Stats Card */}
          <div className="lg:col-span-2 space-y-6">

            {/* LSTM Prediction Engine */}
            <div className={`p-6 rounded-3xl border transition-all ${isCritical ? 'bg-red-500/10 border-red-500/50' : 'bg-slate-900/40 border-slate-800'}`}>
              <div className="flex items-center gap-2 mb-6 text-slate-300">
                <BrainCircuit className="w-6 h-6 text-indigo-400" />
                <h2 className="text-sm font-bold uppercase tracking-widest opacity-90">
                  LSTM AI PREDICTION ENGINE
                </h2>
              </div>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-4 -mt-4">
                Analyzing gas trends and O2 depletion for survival estimation...
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="flex flex-col items-center justify-center p-4 bg-slate-950/50 rounded-2xl border border-slate-800/50">
                  <div className={`text-6xl font-black font-mono tracking-tighter mb-1 ${currentRemaining > 600 ? 'text-emerald-400' : 'text-red-500 animate-pulse'}`}>
                    {currentRemaining > 1800
                      ? "SAFE"
                      : `${String(Math.floor(currentRemaining / 60)).padStart(2, '0')}:${String(currentRemaining % 60).padStart(2, '0')}`
                    }
                  </div>
                  <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">Time to Escape</p>
                </div>

                <div className="space-y-4">
                  <div className="flex justify-between items-center pb-2 border-b border-slate-800/50">
                    <span className="text-xs text-slate-500 font-bold uppercase">LSTM Status</span>
                    <span className={`text-sm font-black ${countdownSeconds !== null && countdownSeconds < 600 ? 'text-red-500' : 'text-emerald-400'}`}>
                      {countdownSeconds !== null
                        ? (countdownSeconds > 1800 ? "WELL" : (countdownSeconds > 600 ? "FATIGUE" : "DANGER"))
                        : "CALCULATING"}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-slate-500 font-bold uppercase">Physio Threshold</span>
                    <span className={`text-sm font-black ${physioSeconds !== null && physioSeconds < 600 ? 'text-red-500' : 'text-emerald-400'}`}>
                      {physioSeconds !== null
                        ? (physioSeconds > 1800 ? "SAFE" : (physioSeconds > 720 ? "FATIGUE" : (physioSeconds > 240 ? "DIZZY" : "CRITICAL")))
                        : "CALCULATING"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <SensorCard
                label="Carbon Dioxide"
                value={currentData.co2}
                unit="ppm"
                trend={history.length > 1 ? currentData.co2 - history[history.length - 2].co2 : 0}
                config={{ ...SENSOR_CONFIG.co2, max: activeThresholds.co2 * 1.5 }}
                isDanger={currentData.co2 > activeThresholds.co2}
              />
              <SensorCard
                label="Carbon Monoxide"
                value={currentData.co}
                unit="ppm"
                trend={history.length > 1 ? currentData.co - history[history.length - 2].co : 0}
                config={{ ...SENSOR_CONFIG.co, max: activeThresholds.co * 2 }}
                isDanger={currentData.co > activeThresholds.co}
              />
              <SensorCard
                label="Oxygen Levels"
                value={currentData.o2}
                unit="%"
                trend={history.length > 1 ? currentData.o2 - history[history.length - 2].o2 : 0}
                config={{ ...SENSOR_CONFIG.o2, min: 15, max: activeThresholds.o2Max }}
                isDanger={currentData.o2 < activeThresholds.o2Min || currentData.o2 > activeThresholds.o2Max}
              />
              <SensorCard
                label="Temperature"
                value={currentData.temperature}
                unit="°C"
                config={SENSOR_CONFIG.temperature}
              />
              <SensorCard
                label="Rel. Humidity"
                value={currentData.humidity}
                unit="%"
                config={SENSOR_CONFIG.humidity}
              />
              <SensorCard
                label="Pressure"
                value={currentData.pressure}
                unit="hPa"
                config={SENSOR_CONFIG.pressure}
              />
            </div>
          </div>

          {/* Side Panel */}
          <div className="space-y-6">
            {/* AI Integrity Analytics */}
            <div className="glass rounded-2xl p-5 border border-slate-800 bg-indigo-500/5">
              <div className="mb-4">
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2 uppercase tracking-widest">
                  <ShieldCheck className="w-4 h-4 text-indigo-400" /> AI System Integrity
                </h3>
              </div>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest mb-1.5 text-slate-400">
                    <span>Model Accuracy</span>
                    <span className="text-white">{currentData.ai_metrics?.accuracy || 98}%</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 transition-all duration-1000"
                      style={{ width: `${currentData.ai_metrics?.accuracy || 98}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest mb-1.5 text-slate-400">
                    <span>Prediction Precision</span>
                    <span className="text-white">{currentData.ai_metrics?.precision || 96}%</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 transition-all duration-1000"
                      style={{ width: `${currentData.ai_metrics?.precision || 96}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Sensor Analytics - CO2 */}
            <div className="glass rounded-2xl p-5 border border-slate-800">
              <div className="mb-4">
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2 uppercase tracking-widest">
                  <TrendingUp className="w-4 h-4 text-emerald-500" /> CO2 Analytics
                </h3>
              </div>
              <div className="h-[150px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={history}>
                    <defs>
                      <linearGradient id="colorCo2" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="timestamp" hide />
                    <YAxis domain={[400, 'auto']} stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px', fontSize: '10px' }} />
                    <Area type="monotone" dataKey="co2" stroke="#10b981" fill="url(#colorCo2)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Sensor Analytics - O2 */}
            <div className="glass rounded-2xl p-5 border border-slate-800">
              <div className="mb-4">
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2 uppercase tracking-widest">
                  <TrendingUp className="w-4 h-4 text-blue-500" /> Oxygen Analytics
                </h3>
              </div>
              <div className="h-[150px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={history}>
                    <defs>
                      <linearGradient id="colorO2" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="timestamp" hide />
                    <YAxis domain={[15, 21]} stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px', fontSize: '10px' }} />
                    <Area type="monotone" dataKey="o2" stroke="#3b82f6" fill="url(#colorO2)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Alerts Log */}
            <div className="glass rounded-2xl p-6 border border-slate-800 max-h-[450px] overflow-hidden flex flex-col">
              <h3 className="text-lg font-semibold text-slate-100 mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-500" /> Active Alerts
              </h3>
              <div className="flex-grow overflow-y-auto space-y-3 pr-2">
                {alerts.length === 0 ? (
                  <p className="text-sm text-slate-600 italic">No alerts recorded.</p>
                ) : (
                  alerts.map(alert => (
                    <div
                      key={alert.id}
                      className={`p-3 rounded-xl border ${alert.type === 'DANGER' ? 'bg-red-500/5 border-red-500/30' : 'bg-amber-500/5 border-amber-500/30'}`}
                    >
                      <div className="flex justify-between items-center mb-1">
                        <p className={`text-[10px] font-black uppercase tracking-tighter ${alert.type === 'DANGER' ? 'text-red-400' : 'text-amber-400'}`}>{alert.type}</p>
                        <span className="text-[10px] text-slate-600">{new Date(alert.timestamp).toLocaleTimeString()}</span>
                      </div>
                      <p className="text-xs text-slate-300">{alert.message}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      <footer className="p-8 text-center text-slate-600 text-xs border-t border-slate-900">
        <p>&copy; 2024 VAAYUU - Advanced Monitoring System</p>
      </footer>
    </div>
  );
};

// --- Sub-components ---

interface SensorCardProps {
  label: string;
  value: number;
  unit: string;
  trend?: number;
  isDanger?: boolean;
  config: {
    color: string;
    min: number;
    max: number;
  };
}

const SensorCard: React.FC<SensorCardProps> = ({ label, value, unit, trend, isDanger, config }) => {
  return (
    <div className={`glass p-4 rounded-xl border transition-all duration-300 ${isDanger
      ? 'border-red-500 bg-red-500/10 shadow-[0_0_20px_rgba(239,68,68,0.2)] animate-pulse'
      : 'border-slate-800 hover:border-slate-700'}`}>
      <div className="flex justify-between items-start mb-2">
        <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className={`text-2xl font-bold mono tracking-tighter ${isDanger ? 'text-red-400' : 'text-white'}`}>
          {value.toFixed(1)}
        </span>
        <span className="text-xs text-slate-500">{unit}</span>
      </div>
      <div className="mt-4 h-1.5 w-full bg-slate-900 rounded-full overflow-hidden border border-slate-800">
        <div
          className={`h-full transition-all duration-1000 ease-out ${isDanger ? 'animate-pulse' : ''}`}
          style={{
            width: `${Math.min(100, Math.max(5, ((value - config.min) / (config.max - config.min)) * 100))}%`,
            backgroundColor: isDanger ? '#ef4444' : config.color
          }}
        />
      </div>
    </div>
  );
};

export default App;
