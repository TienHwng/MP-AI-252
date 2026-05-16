const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3001';
const HERA_API_BASE_URL = import.meta.env.VITE_HERA_API_BASE_URL || 'http://localhost:3002';
export const ACTIVITY_LOG_UPDATED_EVENT = 'hera:activity-log-updated';
const CHAT_SESSION_STORAGE_KEY = 'hera_chat_session';

const SENSOR_ENDPOINTS = [
	'/api/sensors/latest',
	'/sensors/latest',
	'/api/latest',
	'/latest',
];

const DEFAULT_DEVICE_ID = 'device_0001';
const DEFAULT_CHAT_MODEL_NAME = 'H.E.R.A Assistant';

const DEVICE_TARGET_LABELS = {
	main_led: 'LED living room',
	neo_led: 'LED bedroom',
	ws2812: 'LED toilet',
	mini_fan: 'Fan living room',
	relay: 'TV',
	device_0001: 'Yolo Uno',
	system: 'System',
};

const DEVICE_TARGET_ROOMS = {
	main_led: 'Living Room',
	neo_led: 'Bedroom',
	ws2812: 'Toilet',
	mini_fan: 'Living Room',
	relay: 'Living Room',
	device_0001: 'Main Room',
	system: 'System',
};

const RPC_METHOD_TARGETS = {
	setMainLedBrightness: 'main_led',
	setStripBrightness: 'neo_led',
	setWS2812Brightness: 'ws2812',
	setFanSpeed: 'mini_fan',
};

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
		throw new Error(payload.message || payload.error || payload.reason || `${serviceName} request failed: ${response.status}`);
	}
	return payload;
};

const emitActivityLogUpdated = (log) => {
	if (typeof window === 'undefined') return;
	window.dispatchEvent(new CustomEvent(ACTIVITY_LOG_UPDATED_EVENT, { detail: log }));
};

const normalizeActivityLog = (raw = {}) => ({
	id: raw.id || raw.log_id || '',
	logId: raw.log_id || raw.id || '',
	userId: raw.user_id || raw.userId || '',
	userName: raw.user_name || raw.userName || '',
	envId: raw.env_id || raw.envId || '',
	deviceId: raw.device_id || raw.deviceId || '',
	targetId: raw.target_id || raw.targetId || '',
	deviceName: raw.device_name || raw.deviceName || '',
	room: raw.room || '',
	eventType: raw.event_type || raw.eventType || 'system',
	triggerSource: raw.trigger_source || raw.triggerSource || 'system',
	severity: raw.severity || raw.status || 'info',
	status: raw.status || raw.severity || 'info',
	priority: raw.priority ?? 0,
	action: raw.action || '',
	message: raw.message || raw.response_text || '',
	responseText: raw.response_text || raw.message || '',
	actorType: raw.actor_type || raw.actorType || '',
	actorName: raw.actor_name || raw.actorName || raw.user_name || '',
	oldValue: raw.old_value ?? raw.oldValue ?? null,
	newValue: raw.new_value ?? raw.newValue ?? null,
	details: raw.details || {},
	metadata: raw.metadata || {},
	showOnSidebar: raw.show_on_sidebar ?? raw.showOnSidebar ?? true,
	createdAt: raw.createdAt || raw.created_at || null,
	createdAtVn: raw.created_at_vn || raw.createdAtVn || '',
	timestamp: raw.timestamp || (raw.createdAt || raw.created_at ? new Date(raw.createdAt || raw.created_at).getTime() : Date.now()),
});

const appendOptionalParam = (params, key, value) => {
	if (value === undefined || value === null || value === '' || value === 'all') return;
	params.set(key, String(value));
};

const appendActivityFilterParams = (params, filters = {}) => {
	appendOptionalParam(params, 'event_type', filters.eventType || filters.event_type);
	appendOptionalParam(params, 'severity', filters.severity);
	appendOptionalParam(params, 'trigger_source', filters.triggerSource || filters.trigger_source);
	appendOptionalParam(params, 'room', filters.room);
	appendOptionalParam(params, 'target_id', filters.targetId || filters.target_id);
	appendOptionalParam(params, 'search', filters.search);
	appendTimeRangeParam(params, 'from', filters.from);
	appendTimeRangeParam(params, 'to', filters.to);
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

const createChatSessionId = (userId) => {
	const randomPart =
		typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
			? crypto.randomUUID()
			: `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
	return `dashboard_${userId}_${randomPart}`;
};

export const getCurrentChatSessionId = () => {
	const user = getStoredUser();
	if (!user?.user_id) return null;

	const raw = localStorage.getItem(CHAT_SESSION_STORAGE_KEY);
	if (raw) {
		try {
			const session = JSON.parse(raw);
			if (session?.user_id === user.user_id && session?.chat_id) {
				return session.chat_id;
			}
		} catch {
			// Replace invalid local session data with a fresh chat id below.
		}
	}

	const chatId = createChatSessionId(user.user_id);
	localStorage.setItem(
		CHAT_SESSION_STORAGE_KEY,
		JSON.stringify({
			chat_id: chatId,
			user_id: user.user_id,
			created_at: new Date().toISOString(),
		}),
	);
	return chatId;
};

export const logoutUser = () => {
	localStorage.removeItem('hera_user');
	localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
};

export const fetchActivityLogs = async ({
	limit = 15,
	page = 1,
	pageSize,
	surface = 'sidebar',
	filters = {},
	excludeIds = [],
	forceFresh = false,
} = {}) => {
	const user = getStoredUser();
	const params = new URLSearchParams({
		surface,
		page: String(page),
		limit: String(pageSize || limit),
	});

	if (user?.user_id) {
		params.set('user_id', user.user_id);
	}
	appendActivityFilterParams(params, filters);
	const excludedIds = [...new Set(excludeIds.filter(Boolean).map(String))];
	if (excludedIds.length > 0) {
		params.set('exclude_ids', excludedIds.join(','));
	}
	if (forceFresh) {
		params.set('_refresh', String(Date.now()));
	}

	const payload = await fetchJson(`${API_BASE_URL}/api/activity-logs?${params.toString()}`, {
		cache: forceFresh ? 'no-store' : 'default',
		headers: forceFresh
			? {
				'Cache-Control': 'no-cache',
				Pragma: 'no-cache',
			}
			: undefined,
	}, 'Activity log API');
	const items = Array.isArray(payload.items) ? payload.items.map(normalizeActivityLog) : [];
	return {
		items,
		total: Number(payload.total) || items.length,
		page: Number(payload.page) || page,
		pageSize: Number(payload.pageSize) || pageSize || limit,
	};
};

export const recordActivityLog = async (entry = {}) => {
	const user = getStoredUser();
	const payload = {
		user_id: user?.user_id || entry.user_id || 'system',
		user_name: user?.full_name || entry.user_name || '',
		actor_name: user?.full_name || entry.actor_name || entry.actorName || '',
		actor_type: user ? 'user' : 'system',
		env_id: 'env_0001',
		device_id: DEFAULT_DEVICE_ID,
		...entry,
	};
	const response = await fetchJson(`${API_BASE_URL}/api/activity-logs`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify(payload),
	}, 'Activity log API');
	const log = normalizeActivityLog(response.log || response);
	emitActivityLogUpdated(log);
	return log;
};

const tryRecordActivityLog = async (entry) => {
	try {
		return await recordActivityLog(entry);
	} catch (error) {
		console.warn('Failed to record activity log:', error);
		return null;
	}
};

const triggerActorName = (triggerSource, user) => {
	if (triggerSource === 'hera_assistant') return 'H.E.R.A Assistant';
	if (triggerSource === 'automation') return 'H.E.R.A Auto';
	if (triggerSource === 'schedule') return 'Daily Schedule';
	return user?.full_name || 'Dashboard';
};

const triggerActorType = (triggerSource, user) => {
	if (triggerSource === 'hera_assistant') return 'assistant';
	if (triggerSource === 'automation' || triggerSource === 'schedule') return 'automation';
	return user ? 'user' : 'system';
};

const recordDeviceControlActivity = async (deviceTarget, enabled, options = {}) => {
	const user = options.user || getStoredUser();
	const triggerSource = options.triggerSource || 'web_dashboard';
	const actorName = options.actorName || triggerActorName(triggerSource, user);
	const action = enabled ? 'Turned ON' : 'Turned OFF';
	const label = options.deviceName || DEVICE_TARGET_LABELS[deviceTarget] || deviceTarget;

	return tryRecordActivityLog({
		user_id: user?.user_id || 'system',
		user_name: user?.full_name || '',
		env_id: options.envId || 'env_0001',
		device_id: options.deviceId || DEFAULT_DEVICE_ID,
		target_id: deviceTarget,
		device_name: label,
		room: options.room || DEVICE_TARGET_ROOMS[deviceTarget] || 'Main Room',
		event_type: options.eventType || 'control',
		trigger_source: triggerSource,
		severity: options.severity || (enabled ? 'success' : 'neutral'),
		action,
		message: options.message || `${actorName} ${action.toLowerCase()} ${label}.`,
		actor_type: options.actorType || triggerActorType(triggerSource, user),
		actor_name: actorName,
		old_value: options.oldValue ?? null,
		new_value: enabled,
		details: {
			previous_state: options.oldValue ?? null,
			new_state: enabled,
			...(options.details || {}),
		},
		show_on_sidebar: options.showOnSidebar ?? true,
	});
};

const recordRpcActivity = async (method, params, options = {}) => {
	if (options.skipActivityLog) return null;
	const user = options.user || getStoredUser();
	const activity = options.activity || {};
	const targetId = activity.targetId || RPC_METHOD_TARGETS[method] || method;
	const triggerSource = options.triggerSource || activity.triggerSource || 'web_dashboard';
	const actorName = activity.actorName || triggerActorName(triggerSource, user);
	const label = activity.deviceName || DEVICE_TARGET_LABELS[targetId] || method;
	const displayValue = activity.displayValue ?? activity.percentValue ?? params;
	const suffix = activity.unit ? `${displayValue}${activity.unit}` : displayValue;

	return tryRecordActivityLog({
		user_id: user?.user_id || 'system',
		user_name: user?.full_name || '',
		env_id: activity.envId || 'env_0001',
		device_id: activity.deviceId || DEFAULT_DEVICE_ID,
		target_id: targetId,
		device_name: label,
		room: activity.room || DEVICE_TARGET_ROOMS[targetId] || 'Main Room',
		event_type: activity.eventType || 'control',
		trigger_source: triggerSource,
		severity: activity.severity || 'success',
		action: activity.action || 'Value Changed',
		message: activity.message || `${actorName} set ${label} to ${suffix}.`,
		actor_type: activity.actorType || triggerActorType(triggerSource, user),
		actor_name: actorName,
		old_value: activity.oldValue ?? null,
		new_value: displayValue,
		details: {
			method,
			raw_value: params,
			display_value: displayValue,
			...(activity.details || {}),
		},
		show_on_sidebar: activity.showOnSidebar ?? true,
	});
};

const getExecutionTarget = (result = {}) => {
	const raw = result.raw_metadata || result.rawMetadata || {};
	const proposal = raw.proposal || {};
	const args = proposal.arguments || {};
	return (
		result.changed_entities?.[0] ||
		result.unchanged_entities?.[0] ||
		result.failed_entities?.[0] ||
		raw.target ||
		args.device_target ||
		args.light_target ||
		args.sensor ||
		'system'
	);
};

const recordAssistantActivityLogs = async (response, userText) => {
	const user = getStoredUser();
	const results = response?.metadata?.tool_execution_results;
	if (!Array.isArray(results) || results.length === 0) return;

	await Promise.all(results.map((result) => {
		const target = getExecutionTarget(result);
		const capability = result.capability_name || '';
		const isOff = capability === 'turn_off_device';
		const isValueChange = capability === 'set_device_value' || capability === 'set_sensor_value';
		const label = DEVICE_TARGET_LABELS[target] || target;
		const ok = result.ok !== false;
		const action = isValueChange ? 'Value Changed' : isOff ? 'Turned OFF' : 'Turned ON';
		const severity = ok ? (isOff ? 'neutral' : 'success') : 'warning';

		return tryRecordActivityLog({
			user_id: user?.user_id || 'system',
			user_name: user?.full_name || '',
			env_id: 'env_0001',
			device_id: DEFAULT_DEVICE_ID,
			target_id: target,
			device_name: label,
			room: DEVICE_TARGET_ROOMS[target] || 'Main Room',
			event_type: isValueChange && capability === 'set_sensor_value' ? 'system' : 'control',
			trigger_source: 'hera_assistant',
			severity,
			action,
			message: ok
				? `H.E.R.A Assistant ${action.toLowerCase()} ${label}.`
				: `H.E.R.A Assistant could not control ${label}.`,
			actor_type: 'assistant',
			actor_name: 'H.E.R.A Assistant',
			old_value: result.before_state?.[target] ?? null,
			new_value: result.after_state?.[target] ?? null,
			details: {
				user_text: userText,
				capability,
				status: result.status,
				reason: result.reason,
				verification: result.verification,
			},
			show_on_sidebar: true,
		});
	}));
};

const normalizeChatMessage = (raw = {}) => {
	const createdAt = raw.createdAt || raw.created_at || null;
	const metadata = raw.metadata || {};
	return {
		messageId: raw.message_id || raw.messageId || '',
		role: raw.role === 'assistant' || raw.role === 'system' ? raw.role : 'user',
		text: raw.text || raw.content || '',
		createdAt,
		createdAtVn: raw.created_at_vn || raw.createdAtVn || '',
		timestamp: raw.timestamp || (createdAt ? new Date(createdAt).getTime() : Date.now()),
		metadata,
		isError: Boolean(metadata.is_error || raw.is_error || raw.isError),
	};
};

export const fetchAssistantChatHistory = async () => {
	const user = getStoredUser();
	const chatId = getCurrentChatSessionId();
	if (!user?.user_id || !chatId) {
		return { chatId: null, messages: [] };
	}

	const params = new URLSearchParams({ user_id: user.user_id });
	const payload = await fetchJson(
		`${API_BASE_URL}/api/interaction-sessions/${encodeURIComponent(chatId)}?${params.toString()}`,
		{},
		'Interaction session API',
	);
	const messages = Array.isArray(payload.messages)
		? payload.messages.map(normalizeChatMessage)
		: [];
	return { chatId, session: payload.session || null, messages };
};

export const saveAssistantInteraction = async ({
	userText,
	assistantText,
	response = {},
	userCreatedAt,
	assistantCreatedAt,
	userMetadata = {},
	assistantMetadata = {},
} = {}) => {
	const user = getStoredUser();
	const chatId = getCurrentChatSessionId();
	if (!user?.user_id || !chatId || !userText || !assistantText) return null;

	const modelName =
		response?.metadata?.model_name ||
		response?.metadata?.model ||
		response?.agent_name ||
		DEFAULT_CHAT_MODEL_NAME;

	return fetchJson(`${API_BASE_URL}/api/interaction-sessions/messages`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({
			chat_id: chatId,
			user_id: user.user_id,
			user_name: user.full_name || '',
			model_name: modelName,
			env_id: 'env_0001',
			messages: [
				{
					role: 'user',
					text: userText,
					created_at: userCreatedAt || new Date().toISOString(),
					metadata: { source: 'dashboard', ...userMetadata },
				},
				{
					role: 'assistant',
					text: assistantText,
					created_at: assistantCreatedAt || new Date().toISOString(),
					metadata: {
						ok: response?.ok !== false,
						agent_name: response?.agent_name || '',
						tools_used: Array.isArray(response?.tools_used) ? response.tools_used : [],
						confidence: response?.confidence ?? null,
						...assistantMetadata,
					},
				},
			],
		}),
	}, 'Interaction session API');
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

const appendTimeRangeParam = (params, key, value) => {
	if (value === undefined || value === null || value === '') return;

	const numericValue = Number(value);
	if (Number.isFinite(numericValue)) {
		params.set(key, String(numericValue));
		return;
	}

	const parsed = new Date(value);
	if (!Number.isNaN(parsed.getTime())) {
		params.set(key, parsed.toISOString());
	}
};

export const fetchTelemetrySeries = async ({
	deviceId = 'device_0001',
	limit = 10000,
	from,
	to,
} = {}) => {
	const user = getStoredUser();
	if (!user) {
		throw new Error('User not logged in');
	}

	const params = new URLSearchParams({
		user_id: user.user_id,
		device_id: deviceId,
		limit: String(limit),
	});
	appendTimeRangeParam(params, 'from', from);
	appendTimeRangeParam(params, 'to', to);

	const response = await fetch(`${API_BASE_URL}/api/telemetry?${params.toString()}`);
	const payload = await response.json().catch(() => []);
	if (!response.ok) {
		throw new Error(payload.error || 'Failed to fetch telemetry');
	}

	return Array.isArray(payload) ? payload : [];
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

export const controlDeviceState = async (deviceTarget, enabled, options = {}) => {
	const user = getStoredUser();
	const response = await fetchJson(`${HERA_API_BASE_URL}/api/devices/${deviceTarget}/state`, {
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
	if (!options.skipActivityLog) {
		await recordDeviceControlActivity(deviceTarget, enabled, {
			...options,
			user,
		});
	}
	return response;
};

export const writeSensorValue = async (sensor, value, options = {}) => {
	const response = await fetchJson(`${HERA_API_BASE_URL}/api/sensors/${sensor}/value`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({ value }),
	}, 'HERA dashboard API');
	if (!options.skipActivityLog) {
		await tryRecordActivityLog({
			target_id: sensor,
			device_name: `${sensor} sensor`,
			room: options.room || 'Living Room',
			event_type: 'system',
			trigger_source: options.triggerSource || 'simulator',
			severity: 'info',
			action: 'Sensor Value Written',
			message: `Simulator wrote ${sensor} value to ${value}.`,
			actor_type: 'system',
			actor_name: 'MQTT Simulator',
			new_value: value,
			details: { sensor, value },
			show_on_sidebar: options.showOnSidebar ?? false,
		});
	}
	return response;
};

export const sendAssistantMessage = async (text, options = {}) => {
	const user = getStoredUser();
	const chatId = getCurrentChatSessionId();
	const source = options.source === 'voice' ? 'voice' : 'rest';
	const response = await fetchJson(`${HERA_API_BASE_URL}/api/assistant/message`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({
			text,
			user_id: user?.user_id || 'dashboard',
			session_id: chatId || user?.user_id || 'dashboard',
			source,
		}),
	}, 'HERA dashboard API');
	await recordAssistantActivityLogs(response, text);
	return response;
};

export const synthesizeAssistantSpeech = async (text, { lang = 'vi' } = {}) => {
	const response = await fetch(`${HERA_API_BASE_URL}/api/assistant/tts`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({ text, lang }),
	});
	if (!response.ok) {
		const payload = await response.json().catch(() => ({}));
		throw new Error(payload.error || 'Failed to synthesize voice reply');
	}
	return response.blob();
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

export const sendRpcCommand = async (method, params, options = {}) => {
	const user = getStoredUser();
	const response = await fetchJson(`${HERA_API_BASE_URL}/api/rpc`, {
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
	await recordRpcActivity(method, params, {
		...options,
		user,
	});
	return response;
};
