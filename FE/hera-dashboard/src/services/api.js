const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001';
const HERA_API_BASE_URL = import.meta.env.VITE_HERA_API_BASE_URL || 'http://localhost:3002';

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

const serviceOrigin = (url) => {
	try {
		return new URL(url).origin;
	} catch {
		return url;
	}
};

const fetchJson = async (url, options = {}, serviceName = 'API service') => {
	let response;
	try {
		response = await fetch(url, options);
	} catch {
		throw new Error(`${serviceName} is not reachable at ${serviceOrigin(url)}.`);
	}

	const payload = await response.json().catch(() => ({}));
	if (!response.ok) {
		throw new Error(payload.error || payload.reason || `${serviceName} request failed: ${response.status}`);
	}
	return payload;
};

const normalizeSensorData = (raw = {}) => {
	const sensors = raw.sensors ?? {};
	const devices = raw.devices ?? {};
	const network = raw.network ?? {};
	const runtime = raw.runtime ?? {};

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
		mode: runtime.mode ?? raw.metadata?.mode ?? raw.mode ?? null,
		source: runtime.source_kind ?? raw.metadata?.source ?? raw.source ?? null,
		last_seen_at: raw.last_seen_at ?? raw.recorded_at ?? raw.timestamp ?? null,
		metadata: raw.metadata ?? {},
		runtime,
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
				chart_timestamp: payload.chart_timestamp ?? payload.chartTimestamp ?? payload.timestamp,
				chart_recorded_at: payload.chart_recorded_at ?? payload.chartRecordedAt ?? payload.recorded_at,
				chart_time: payload.chart_time ?? payload.chartTime ?? payload.time,
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
	return controlDeviceState('main_led', enabled);
};

export const toggleNeoLight = async (enabled) => {
	return controlDeviceState('neo_led', enabled);
};

export const controlDeviceState = async (deviceTarget, enabled) => {
	const user = getStoredUser();
	return fetchJson(`${HERA_API_BASE_URL}/api/devices/${deviceTarget}/state`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({
			state: enabled,
			user_id: user?.user_id || 'dashboard',
			session_id: user?.user_id || 'dashboard',
		}),
	}, 'HERA dashboard API');
};

export const writeSensorValue = async (sensor, value) => {
	return fetchJson(`${HERA_API_BASE_URL}/api/sensors/${sensor}/value`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({ value }),
	}, 'HERA dashboard API');
};

export const sendAssistantMessage = async (text) => {
	const user = getStoredUser();
	return fetchJson(`${HERA_API_BASE_URL}/api/assistant/message`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({
			text,
			user_id: user?.user_id || 'dashboard',
			session_id: user?.user_id || 'dashboard',
		}),
	}, 'HERA dashboard API');
};

export const fetchRuntimeStatus = async () => {
	return fetchJson(`${HERA_API_BASE_URL}/api/runtime/status`, {}, 'HERA dashboard API');
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
