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
	const sensors = raw.sensors ?? {};
	const devices = raw.devices ?? {};
	const network = raw.network ?? {};

	const timestamp =
		raw.recorded_at ||
		raw.timestamp ||
		raw.updated_at ||
		raw.updatedAt ||
		raw.created_at ||
		Date.now();

	return {
		temperature: toNullableNumber(sensors.temperature ?? raw.temperature ?? raw.temp),
		humidity: toNullableNumber(sensors.humidity ?? raw.humidity ?? raw.humi),
		light: toNullableNumber(sensors.light ?? raw.light ?? raw.lux),
		airQualityIndex: toNullableNumber(sensors.air_quality ?? raw.air_quality ?? raw.airQuality ?? raw.aqi),
		gasPpm: toNullableNumber(sensors.gas_ppm ?? raw.gas_ppm ?? raw.gasPpm ?? raw.gas),
		gasDetected: Boolean(sensors.gas_detected ?? raw.gas_detected ?? raw.gasDetected),
		updatedAt: timestamp,
		led_state: devices.led_status ?? raw.led_state ?? false,
		neo_led_state: devices.neo_led_status ?? raw.neo_led_state ?? false,
		ws2812_status: devices.ws2812_status ?? false,
		relay_status: devices.relay_status ?? false,
		mini_fan_status: devices.mini_fan_status ?? false,
		wifi_connected: network.wifi_connected ?? false,
		mqtt_connected: network.mqtt_connected ?? false,
		wifi_rssi: toNullableNumber(network.wifi_rssi),
		uptime_ms: toNullableNumber(network.uptime_ms),
		inference_result: toNullableNumber(sensors.anomaly ?? raw.inference_result),
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