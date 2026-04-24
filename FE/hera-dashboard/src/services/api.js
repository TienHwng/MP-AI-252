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

export const loginUser = async (email, password) => {
	const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({ email, password }),
	});

	const payload = await response.json();

	if (!response.ok) {
		throw new Error(payload.error || 'Login failed');
	}

	localStorage.setItem('hera_user', JSON.stringify(payload.user));
	return payload.user;
};

export const getStoredUser = () => {
	const raw = localStorage.getItem('hera_user');
	if (!raw) return null;

	try {
		return JSON.parse(raw);
	} catch {
		return null;
	}
};

export const logoutUser = () => {
	localStorage.removeItem('hera_user');
};

// Khai báo việc User này vừa tiếp quản thiết bị
export const claimDevice = async (userId, deviceId = 'device_0001') => {
	try {
		await fetch(`${API_BASE_URL}/api/device/claim`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ user_id: userId, device_id: deviceId }),
		});
	} catch (error) {
		console.error("Failed to claim device:", error);
	}
};

export const fetchLatestSensorData = async () => {
	let lastError = null;
    const user = getStoredUser();
    
    if (!user) {
        throw new Error('User not logged in');
    }

    // Đính kèm user_id vào params để lọc data đúng user
    const queryParams = `?user_id=${user.user_id}&device_id=device_0001`;

	for (const endpoint of SENSOR_ENDPOINTS) {
		try {
			const response = await fetch(`${API_BASE_URL}${endpoint}${queryParams}`);
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

export const subscribeLatestSensorData = ({ onData, onError } = {}) => {
	const user = getStoredUser();
	if (!user) {
		throw new Error('User not logged in');
	}

	const params = new URLSearchParams({
		user_id: user.user_id,
		device_id: 'device_0001',
	});
	const source = new EventSource(`${API_BASE_URL}/api/sensors/stream?${params.toString()}`);

	source.addEventListener('telemetry', (event) => {
		try {
			const payload = JSON.parse(event.data);
			onData?.(normalizeSensorData(payload));
		} catch (error) {
			onError?.(error);
		}
	});

	source.onerror = (error) => {
		onError?.(error);
	};

	return () => source.close();
};

export const subscribeTelemetrySeries = ({ limit = 500, onData, onError } = {}) => {
	const user = getStoredUser();
	if (!user) {
		throw new Error('User not logged in');
	}

	const params = new URLSearchParams({
		user_id: user.user_id,
		device_id: 'device_0001',
	});
	const source = new EventSource(`${API_BASE_URL}/api/sensors/stream?${params.toString()}`);

	source.addEventListener('telemetry', (event) => {
		try {
			const payload = JSON.parse(event.data);
			const point = {
				id: payload.id,
				timestamp: payload.timestamp,
				recorded_at: payload.recorded_at,
				time: payload.time,
				temp: payload.sensors?.temperature ?? payload.temp ?? null,
				humidity: payload.sensors?.humidity ?? payload.humidity ?? null,
				light: payload.sensors?.light ?? payload.light ?? null,
			};
			onData?.(point, limit);
		} catch (error) {
			onError?.(error);
		}
	});

	source.onerror = (error) => {
		onError?.(error);
	};

	return () => source.close();
};

export const toggleLedLight = async (enabled) => {
	const response = await fetch(`${API_BASE_URL}/api/control/led`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({ enabled }),
	});

	if (!response.ok) {
		throw new Error(`Failed to toggle LED light: ${response.status}`);
	}

	return response.json();
};

export const toggleNeoLight = async (enabled) => {
	const response = await fetch(`${API_BASE_URL}/api/control/neon`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({ enabled }),
	});

	if (!response.ok) {
		throw new Error(`Failed to toggle neon light: ${response.status}`);
	}

	return response.json();
};

const MODEL_SETTING_FIELDS = [
	'orchestratorModel',
	'deviceControlModel',
	'sensorAnalysisModel',
	'anomalyExpertModel',
];

const normalizeProviderModels = (providerModels = {}) => {
	const normalized = {};
	for (const field of MODEL_SETTING_FIELDS) {
		normalized[field] = typeof providerModels[field] === 'string' ? providerModels[field] : '';
	}
	return normalized;
};

const normalizeModelSettings = (payload = {}) => {
	const provider = payload.provider === 'ollama' ? 'ollama' : 'openrouter';
	return {
		provider,
		models: {
			ollama: normalizeProviderModels(payload.models?.ollama),
			openrouter: normalizeProviderModels(payload.models?.openrouter),
		},
		updatedAt: typeof payload.updatedAt === 'string' ? payload.updatedAt : '',
	};
};

export const fetchModelSettings = async () => {
	const response = await fetch(`${API_BASE_URL}/api/settings/models`);
	const payload = await response.json();
	if (!response.ok) {
		throw new Error(payload.error || 'Failed to fetch model settings');
	}
	return normalizeModelSettings(payload);
};

export const updateModelSettings = async (settings) => {
	const response = await fetch(`${API_BASE_URL}/api/settings/models`, {
		method: 'PUT',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify(settings),
	});
	const payload = await response.json();
	if (!response.ok) {
		throw new Error(payload.error || 'Failed to save model settings');
	}
	return normalizeModelSettings(payload.settings || settings);
};
