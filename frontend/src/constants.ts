
import { Thresholds } from './types';

export const BUILDING_THRESHOLDS: Thresholds = {
  co2: 1000,     // User: >1000 ppm is Poor Air
  co: 9,         // User: >9 ppm is Unsafe
  o2Min: 19.5,   // User: <19.5% starts Fatigue/Escape countdown
  o2Max: 23.5,
  tempMin: 18,
  tempMax: 28
};

export const VEHICLE_THRESHOLDS: Thresholds = {
  co2: 1500,     // User: >1500 is Dangerous (drowsiness)
  co: 9,
  o2Min: 19.5,
  o2Max: 23.5,
  tempMin: 15,
  tempMax: 40
};

/**
 * Descriptive maps based on User's provided tables
 */
export const CO2_STATUS = [
  { min: 0, max: 450, status: 'Normal', desc: 'Outdoor fresh air', color: 'text-green-500' },
  { min: 451, max: 800, status: 'Good', desc: 'Well-ventilated indoor space', color: 'text-green-400' },
  { min: 801, max: 1000, status: 'Acceptable', desc: 'Mild drowsiness possible', color: 'text-yellow-500' },
  { min: 1001, max: 1500, status: 'Poor Air', desc: 'Fatigue, reduced concentration', color: 'text-orange-500' },
  { min: 1501, max: 5000, status: 'Dangerous', desc: 'Headache, sleepiness', color: 'text-red-500' },
  { min: 5001, max: 1000000, status: 'Critical', desc: 'Oxygen deprivation risk', color: 'text-purple-600' },
];

export const CO_STATUS = [
  { min: 0, max: 2, status: 'Normal', desc: 'Fresh / Well-ventilated air', color: 'text-green-500' },
  { min: 3, max: 9, status: 'Elevated', desc: 'Acceptable for short periods', color: 'text-yellow-500' },
  { min: 10, max: 30, status: 'Unsafe', desc: 'Headache, dizziness after hours', color: 'text-orange-500' },
  { min: 31, max: 50, status: 'Dangerous', desc: 'Nausea, fatigue (1-2 hours)', color: 'text-red-500' },
  { min: 51, max: 200, status: 'Critical', desc: 'Serious poisoning emergency', color: 'text-purple-600' },
  { min: 201, max: 1000, status: 'Fatal', desc: 'Life-threatening minutes', color: 'text-black font-bold text-xl' },
];

export const O2_STATUS = [
  { min: 19.5, max: 100, status: 'Normal', time: '60 min', color: 'text-green-500' },
  { min: 17, max: 19.49, status: 'Fatigue', time: '12 min', color: 'text-yellow-500' },
  { min: 14, max: 16.99, status: 'Dizziness', time: '4 min', color: 'text-orange-500' },
  { min: 10, max: 13.99, status: 'Fainting', time: '1.5 min', color: 'text-red-500' },
  { min: 0, max: 9.99, status: 'Collapse', time: '30 sec', color: 'text-purple-600' },
];

export const SENSOR_CONFIG = {
  co2: { label: 'CO2', unit: 'ppm', min: 400, max: 5000, color: '#10b981' },
  co: { label: 'CO', unit: 'ppm', min: 0, max: 200, color: '#f59e0b' },
  o2: { label: 'O2', unit: '%', min: 15, max: 25, color: '#3b82f6' },
  temperature: { label: 'Temp', unit: '°C', min: -10, max: 50, color: '#ef4444' },
  humidity: { label: 'Humidity', unit: '%', min: 0, max: 100, color: '#8b5cf6' },
  pressure: { label: 'Pressure', unit: 'hPa', min: 900, max: 1100, color: '#6366f1' },
};
