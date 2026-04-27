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

const isPlainObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

const scalarValue = (value) => {
	if (isPlainObject(value) && Object.prototype.hasOwnProperty.call(value, 'value')) {
		return value.value;
	}
	return value;
};

const firstPresent = (...values) => values.find((value) => value !== undefined && value !== null);

const toNullableScalarNumber = (value) => toNullableNumber(scalarValue(value));

const toNullableBoolean = (value) => {
	const scalar = scalarValue(value);
	if (typeof scalar === 'boolean') return scalar;
	if (typeof scalar === 'number') {
		if (scalar === 1) return true;
		if (scalar === 0) return false;
	}
	if (typeof scalar === 'string') {
		const normalized = scalar.trim().toLowerCase();
		if (['1', 'true', 'on', 'active'].includes(normalized)) return true;
		if (['0', 'false', 'off', 'inactive'].includes(normalized)) return false;
	}
	return null;
};

const normalizeNestedSensors = (raw = {}) => {
	const sensors = raw.sensors ?? {};
	const dht20 = isPlainObject(sensors.dht20) ? sensors.dht20 : {};
	const light = isPlainObject(sensors.light) ? sensors.light : {};
	const gas = isPlainObject(sensors.gas) ? sensors.gas : {};

	return {
		...sensors,
		dht20: {
			...dht20,
			temperature: toNullableScalarNumber(firstPresent(dht20.temperature, sensors.temperature, raw.temperature, raw.temp)),
			humidity: toNullableScalarNumber(firstPresent(dht20.humidity, sensors.humidity, raw.humidity, raw.humi)),
		},
		light: {
			...light,
			value: toNullableScalarNumber(firstPresent(light.value, sensors.light, raw.light, raw.lux)),
		},
		gas: {
			...gas,
			value: toNullableScalarNumber(firstPresent(gas.value, sensors.gas, sensors.gas_ppm, raw.gas_ppm, raw.gasPpm, raw.gas)),
			detected: toNullableBoolean(firstPresent(gas.detected, gas.gas_detected, sensors.gas_detected, raw.gas_detected, raw.gasDetected)),
		},
	};
};

const normalizeNestedDevices = (raw = {}) => {
	const devices = raw.devices ?? {};
	const led = isPlainObject(devices.led) ? devices.led : {};
	const neoLed = isPlainObject(devices.neo_led) ? devices.neo_led : {};
	const ws2812 = isPlainObject(devices.ws2812) ? devices.ws2812 : {};
	const relay = isPlainObject(devices.relay) ? devices.relay : {};
	const miniFan = isPlainObject(devices.mini_fan) ? devices.mini_fan : {};

	return {
		...devices,
		led: {
			...led,
			status: toNullableBoolean(firstPresent(led.status, devices.led_status, raw.led_state)),
		},
		neo_led: {
			...neoLed,
			status: toNullableBoolean(firstPresent(neoLed.status, devices.neo_led_status, raw.neo_led_state)),
			brightness: toNullableScalarNumber(firstPresent(neoLed.brightness, devices.strip_brightness)),
		},
		ws2812: {
			...ws2812,
			status: toNullableBoolean(firstPresent(ws2812.status, devices.ws2812_status)),
			brightness: toNullableScalarNumber(firstPresent(ws2812.brightness, devices.ws2812_brightness)),
		},
		relay: {
			...relay,
			status: toNullableBoolean(firstPresent(relay.status, devices.relay_status)),
		},
		mini_fan: {
			...miniFan,
			status: toNullableBoolean(firstPresent(miniFan.status, devices.mini_fan_status)),
			speed: toNullableScalarNumber(firstPresent(miniFan.speed, devices.fan_speed)),
		},
	};
};

export const getSensorValue = (telemetry, sensor) => {
	const sensors = telemetry?.sensors ?? telemetry ?? {};
	if (sensor === 'temperature') return sensors.dht20?.temperature ?? sensors.temperature ?? null;
	if (sensor === 'humidity') return sensors.dht20?.humidity ?? sensors.humidity ?? null;
	if (sensor === 'light') return scalarValue(sensors.light) ?? null;
	if (sensor === 'gas' || sensor === 'gas_ppm') return scalarValue(sensors.gas ?? sensors.gas_ppm) ?? null;
	if (sensor === 'gas_detected') return sensors.gas?.detected ?? sensors.gas_detected ?? null;
	if (sensor === 'anomaly') return sensors.anomaly ?? sensors.anomaly_score ?? null;
	return scalarValue(sensors[sensor]) ?? null;
};

export const getDeviceStatus = (telemetry, target) => {
	const devices = telemetry?.devices ?? telemetry ?? {};
	const deviceKey = {
		main_led: 'led',
		neo_led: 'neo_led',
		ws2812: 'ws2812',
		relay: 'relay',
		mini_fan: 'mini_fan',
	}[target] || target;
	const nested = devices[deviceKey];
	if (isPlainObject(nested)) return nested.status ?? null;
	if (typeof nested === 'boolean') return nested;
	return devices[`${deviceKey}_status`] ?? null;
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
	const sensors = normalizeNestedSensors(raw);
	const devices = normalizeNestedDevices(raw);
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
		...raw,
		sensors,
		devices,
		network,
		runtime,
		updatedAt: timestamp,
		wifi_connected: network.wifi_connected ?? false,
		mqtt_connected: network.mqtt_connected ?? false,
		wifi_rssi: toNullableNumber(network.wifi_rssi),
		uptime_ms: toNullableNumber(network.uptime_ms),
		mode: runtime.mode ?? raw.metadata?.mode ?? raw.mode ?? null,
		source: runtime.source_kind ?? raw.metadata?.source ?? raw.source ?? null,
		last_seen_at: raw.last_seen_at ?? raw.recorded_at ?? raw.timestamp ?? null,
		metadata: raw.metadata ?? {},
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
				sensors: normalizeNestedSensors(payload),
				devices: normalizeNestedDevices(payload),
				network: payload.network ?? {},
				runtime: payload.runtime ?? {},
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

export const sendRpcCommand = async (method, params) => {
	const user = getStoredUser();
	return fetchJson(`${HERA_API_BASE_URL}/api/rpc`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({
			method,
			params,
			user_id: user?.user_id || 'dashboard',
			session_id: user?.user_id || 'dashboard',
		}),
	}, 'HERA dashboard API');
};