const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001';

const SENSOR_ENDPOINTS = [
	'/api/sensors/latest',
	'/sensors/latest',
	'/api/latest',
	'/latest',
];

const toNullableNumber = (value) => {
	if (value === null || value === undefined || value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
};

const normalizeSensorData = (raw = {}) => {
	const timestamp =
		raw.timestamp ||
		raw.updated_at ||
		raw.updatedAt ||
		raw.created_at ||
		raw.recorded_at ||
		Date.now();

	return {
		temperature: toNullableNumber(raw.temperature ?? raw.temp),
		humidity: toNullableNumber(raw.humidity ?? raw.humi),
		light: toNullableNumber(raw.light ?? raw.lux),
		airQualityIndex: toNullableNumber(raw.air_quality ?? raw.airQuality ?? raw.aqi),
		gasPpm: toNullableNumber(raw.gas_ppm ?? raw.gasPpm ?? raw.gas),
		gasDetected: Boolean(raw.gas_detected ?? raw.gasDetected),
		updatedAt: timestamp,
		led_state: raw.led_state ?? false,
		neo_led_state: raw.neo_led_state ?? false,
		inference_result: toNullableNumber(raw.inference_result),
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