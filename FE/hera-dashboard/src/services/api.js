const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

const SENSOR_ENDPOINTS = [
	'/api/sensors/latest',
	'/sensors/latest',
	'/api/latest',
	'/latest',
];

const toNumber = (value, fallback = 0) => {
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizeSensorData = (raw = {}) => {
	const timestamp = raw.timestamp || raw.updated_at || raw.updatedAt || raw.created_at || Date.now();

	return {
		temperature: toNumber(raw.temperature ?? raw.temp, 0),
		humidity: toNumber(raw.humidity ?? raw.humi, 0),
		light: toNumber(raw.light ?? raw.lux, 0),
		airQualityIndex: toNumber(raw.air_quality ?? raw.airQuality ?? raw.aqi, 0),
		gasPpm: toNumber(raw.gas_ppm ?? raw.gasPpm ?? raw.gas, 0),
		gasDetected: Boolean(raw.gas_detected ?? raw.gasDetected),
		updatedAt: timestamp,
		raw,
	};
};

export const fetchLatestSensorData = async () => {
	let lastError = null;

	for (const endpoint of SENSOR_ENDPOINTS) {
		try {
			const response = await fetch(`${API_BASE_URL}${endpoint}`);
			if (!response.ok) {
				lastError = new Error(`Request failed: ${response.status}`);
				continue;
			}

			const payload = await response.json();
			return normalizeSensorData(payload);
		} catch (error) {
			lastError = error;
		}
	}

	throw lastError || new Error('Unable to fetch latest sensor data');
};