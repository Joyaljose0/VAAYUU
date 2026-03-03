
export type EnvironmentType = 'VEHICLE' | 'BUILDING';

export interface SensorData {
  timestamp: number;
  temperature: number; // °C
  pressure: number;    // hPa
  humidity: number;    // %
  co2: number;         // ppm
  co: number;          // ppm
  o2: number;          // %
  escape_time?: number;
  backend_alerts?: string[];
  is_warming_up?: boolean;
  ai_metrics?: {
    accuracy: number;
    precision: number;
  };
}

export interface Thresholds {
  co2: number;
  co: number;
  o2Min: number;
  o2Max: number;
  tempMin: number;
  tempMax: number;
}

export interface Alert {
  id: string;
  type: 'WARNING' | 'DANGER' | 'INFO';
  sensor: keyof SensorData;
  message: string;
  timestamp: number;
  value: number;
}

export interface PredictionResult {
  predictedStatus: 'SAFE' | 'UNSAFE' | 'CRITICAL';
  estimatedNextValues: Partial<SensorData>;
  recommendation: string;
  confidence: number;
}
