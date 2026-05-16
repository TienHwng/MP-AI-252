const express = require("express");
const cors = require("cors");
const { MongoClient } = require("mongodb");
const fs = require("fs/promises");
const path = require("path");

const app = express();
app.use(cors());
app.use(express.json());

const MONGODB_URI = process.env.MONGODB_URI || "mongodb://localhost:27017";
const MONGODB_DB = process.env.MONGODB_DB || "HERA";
const client = new MongoClient(MONGODB_URI);
let collection; // telemetry_points
let usersCollection;
let modelSettingsCollection;
let devicesCollection; // Thêm collection devices
let activityLogsCollection;
let interactionSessionsCollection;

const ENV_PATH = path.resolve(__dirname, "../../.env");
const MODEL_SETTINGS_DOC_ID = "hera_model_settings";
const ANSI = {
	reset: "\x1b[0m",
	green: "\x1b[32m",
	yellow: "\x1b[33m",
	red: "\x1b[31m",
};
const VN_TIMEZONE = "Asia/Ho_Chi_Minh";
const TELEMETRY_BUCKET_MS = 5 * 1000;
const MAX_TELEMETRY_LIMIT = 20000;
const DEFAULT_ENV_ID = "env_0001";
const DEFAULT_DEVICE_ID = "device_0001";
const DEFAULT_CHAT_MODEL_NAME = "H.E.R.A Assistant";
const DEFAULT_ACTIVITY_LOG_LIMIT = 15;
const MAX_ACTIVITY_LOG_LIMIT = 100;
const MAX_ACTIVITY_EXCLUDE_IDS = 200;
const ACTIVITY_LOG_DEDUPE_WINDOW_MS = 15 * 60 * 1000;
const CHAT_MESSAGE_ROLES = new Set(["user", "assistant", "system"]);
const DEFAULT_SENSOR_THRESHOLD_CONFIG = {
	temperatureMin: 25,
	temperatureMax: 35,
	temperatureDangerMin: 20,
	temperatureDangerMax: 40,
	humidityMin: 60,
	humidityMax: 80,
	lightMin: null,
	lightMax: 500,
	gasMax: 300,
};
let sensorThresholdConfig = { ...DEFAULT_SENSOR_THRESHOLD_CONFIG };

const ACTIVITY_SEVERITY_PRIORITY = {
	danger: 4,
	alert: 4,
	warning: 3,
	success: 2,
	info: 1,
	neutral: 0,
};

const ACTIVITY_SEVERITIES = new Set([
	"info",
	"success",
	"neutral",
	"warning",
	"danger",
	"alert",
]);

const DEVICE_TARGET_LABELS = {
	main_led: "LED living room",
	neo_led: "LED bedroom",
	ws2812: "LED toilet",
	mini_fan: "Fan living room",
	relay: "TV",
	device_0001: "Yolo Uno",
	system: "System",
};

const DEFAULT_MODEL_SETTINGS = {
	provider: "openrouter",
	models: {
		ollama: {
			orchestratorModel: "qwen2.5:1.5b",
			deviceControlModel: "qwen2.5:7b",
			sensorAnalysisModel: "qwen2.5:7b",
			anomalyExpertModel: "qwen2.5:7b",
		},
		openrouter: {
			orchestratorModel: "qwen/qwen-2.5-7b-instruct",
			deviceControlModel: "qwen/qwen-2.5-7b-instruct",
			sensorAnalysisModel: "qwen/qwen-2.5-7b-instruct",
			anomalyExpertModel: "qwen/qwen-2.5-7b-instruct",
		},
	},
};

const MODEL_SETTING_FIELDS = [
	"orchestratorModel",
	"deviceControlModel",
	"sensorAnalysisModel",
	"anomalyExpertModel",
];

const ENV_TO_PAYLOAD_MAPPING = {
	ollama: {
		provider: "LLM_PROVIDER",
		orchestratorModel: "ORCHESTRATOR_MODEL_OLLAMA",
		deviceControlModel: "DEVICE_AGENT_MODEL_OLLAMA",
		sensorAnalysisModel: "SENSOR_AGENT_MODEL_OLLAMA",
		anomalyExpertModel: "ANOMALY_AGENT_MODEL_OLLAMA",
	},
	openrouter: {
		provider: "LLM_PROVIDER",
		orchestratorModel: "ORCHESTRATOR_MODEL_OPENROUTER",
		deviceControlModel: "DEVICE_AGENT_MODEL_OPENROUTER",
		sensorAnalysisModel: "SENSOR_AGENT_MODEL_OPENROUTER",
		anomalyExpertModel: "ANOMALY_AGENT_MODEL_OPENROUTER",
	},
};

const parseEnv = (content) => {
	const parsed = {};
	const lines = content.split(/\r?\n/);

	for (const rawLine of lines) {
		const line = rawLine.trim();
		if (!line || line.startsWith("#")) continue;
		const equalIndex = line.indexOf("=");
		if (equalIndex <= 0) continue;
		const key = line.slice(0, equalIndex).trim();
		const valuePart = line.slice(equalIndex + 1);
		const inlineCommentIndex = valuePart.indexOf(" #");
		const value = (
			inlineCommentIndex >= 0
				? valuePart.slice(0, inlineCommentIndex)
				: valuePart
		).trim();
		parsed[key] = value;
	}

	return parsed;
};

const pickModelFields = (providerModels = {}) => {
	const result = {};
	for (const field of MODEL_SETTING_FIELDS) {
		if (typeof providerModels[field] === "string") {
			result[field] = providerModels[field];
		}
	}
	return result;
};

const buildModelSettingsPayload = (source = {}) => ({
	provider:
		source.provider === "ollama" || source.provider === "openrouter"
			? source.provider
			: DEFAULT_MODEL_SETTINGS.provider,
	models: {
		ollama: {
			...DEFAULT_MODEL_SETTINGS.models.ollama,
			...pickModelFields(source.models?.ollama || {}),
		},
		openrouter: {
			...DEFAULT_MODEL_SETTINGS.models.openrouter,
			...pickModelFields(source.models?.openrouter || {}),
		},
	},
});

const toVnTimestamp = (value) => {
	if (!value) return "";
	const date = value instanceof Date ? value : new Date(value);
	if (Number.isNaN(date.getTime())) return "";
	return date.toLocaleString("vi-VN", {
		timeZone: VN_TIMEZONE,
		hour12: false,
		year: "numeric",
		month: "2-digit",
		day: "2-digit",
		hour: "2-digit",
		minute: "2-digit",
		second: "2-digit",
	});
};

const toValidDate = (value) => {
	if (!value) return null;
	const date = value instanceof Date ? value : new Date(value);
	return Number.isNaN(date.getTime()) ? null : date;
};

const parseDateQuery = (value) => {
	if (value === undefined || value === null || value === "") return null;

	const numericValue = Number(value);
	const date = Number.isFinite(numericValue)
		? new Date(numericValue)
		: new Date(value);

	return Number.isNaN(date.getTime()) ? null : date;
};

const hasQueryValue = (value) => value !== undefined && value !== null && value !== "";

const parseTelemetryLimit = (value, fallback = 300) => {
	const parsed = Number(value);
	if (!Number.isFinite(parsed)) return fallback;
	return Math.min(Math.max(Math.trunc(parsed), 1), MAX_TELEMETRY_LIMIT);
};

const parseActivityLimit = (value, fallback = DEFAULT_ACTIVITY_LOG_LIMIT) => {
	const parsed = Number(value);
	if (!Number.isFinite(parsed)) return fallback;
	return Math.min(Math.max(Math.trunc(parsed), 1), MAX_ACTIVITY_LOG_LIMIT);
};

const parseActivityPage = (value) => {
	const parsed = Number(value);
	if (!Number.isFinite(parsed)) return 1;
	return Math.max(Math.trunc(parsed), 1);
};

const floorToTelemetryBucket = (value) => {
	const date = toValidDate(value);
	if (!date) return null;
	return new Date(Math.floor(date.getTime() / TELEMETRY_BUCKET_MS) * TELEMETRY_BUCKET_MS);
};

const isPlainObject = (value) =>
	value !== null && typeof value === "object" && !Array.isArray(value);

const firstPresent = (...values) =>
	values.find((value) => value !== undefined && value !== null);

const scalarValue = (value) => {
	if (isPlainObject(value) && Object.prototype.hasOwnProperty.call(value, "value")) {
		return value.value;
	}
	return value;
};

const toNullableNumber = (value) => {
	const scalar = scalarValue(value);
	if (scalar === null || scalar === undefined || scalar === "" || typeof scalar === "boolean") {
		return null;
	}
	const parsed = Number(scalar);
	return Number.isFinite(parsed) ? parsed : null;
};

const envNumber = (envValues, keys, fallback = null) => {
	for (const key of keys) {
		const parsed = toNullableNumber(firstPresent(process.env[key], envValues[key]));
		if (parsed !== null) return parsed;
	}
	return fallback;
};

const normalizeRange = (min, max) => {
	if (min !== null && max !== null && min > max) {
		return { min: max, max: min };
	}
	return { min, max };
};

const buildSensorThresholdConfig = (envValues = {}) => {
	const temperature = normalizeRange(
		envNumber(envValues, ["NORMAL_TEMP_MIN"], DEFAULT_SENSOR_THRESHOLD_CONFIG.temperatureMin),
		envNumber(envValues, ["NORMAL_TEMP_MAX"], DEFAULT_SENSOR_THRESHOLD_CONFIG.temperatureMax),
	);
	const humidity = normalizeRange(
		envNumber(envValues, ["NORMAL_HUMI_MIN", "NORMAL_HUMIDITY_MIN"], DEFAULT_SENSOR_THRESHOLD_CONFIG.humidityMin),
		envNumber(envValues, ["NORMAL_HUMI_MAX", "NORMAL_HUMIDITY_MAX"], DEFAULT_SENSOR_THRESHOLD_CONFIG.humidityMax),
	);
	const light = normalizeRange(
		envNumber(envValues, ["NORMAL_LIGHT_MIN", "LIGHT_MIN", "SIM_LIGHT_MIN"], DEFAULT_SENSOR_THRESHOLD_CONFIG.lightMin),
		envNumber(envValues, ["NORMAL_LIGHT_MAX", "LIGHT_MAX", "SIM_LIGHT_MAX"], DEFAULT_SENSOR_THRESHOLD_CONFIG.lightMax),
	);

	return {
		temperatureMin: temperature.min,
		temperatureMax: temperature.max,
		temperatureDangerMin: envNumber(
			envValues,
			["NORMAL_TEMP_DANGER_MIN", "TEMP_DANGER_MIN", "CRITICAL_TEMP_MIN"],
			temperature.min === null ? DEFAULT_SENSOR_THRESHOLD_CONFIG.temperatureDangerMin : temperature.min - 5,
		),
		temperatureDangerMax: envNumber(
			envValues,
			["NORMAL_TEMP_DANGER_MAX", "TEMP_DANGER_MAX", "CRITICAL_TEMP_MAX"],
			temperature.max === null ? DEFAULT_SENSOR_THRESHOLD_CONFIG.temperatureDangerMax : temperature.max + 5,
		),
		humidityMin: humidity.min,
		humidityMax: humidity.max,
		lightMin: light.min,
		lightMax: light.max,
		gasMax: envNumber(
			envValues,
			["NORMAL_GAS_MAX", "GAS_MAX", "SIM_GAS_DETECTED_THRESHOLD"],
			DEFAULT_SENSOR_THRESHOLD_CONFIG.gasMax,
		),
	};
};

const loadSensorThresholdConfig = async () => {
	try {
		const envContent = await fs.readFile(ENV_PATH, "utf8");
		sensorThresholdConfig = buildSensorThresholdConfig(parseEnv(envContent));
	} catch {
		sensorThresholdConfig = buildSensorThresholdConfig();
	}
};

const toNullableBoolean = (value) => {
	const scalar = scalarValue(value);
	if (typeof scalar === "boolean") return scalar;
	if (typeof scalar === "number") {
		if (scalar === 1) return true;
		if (scalar === 0) return false;
	}
	if (typeof scalar === "string") {
		const normalized = scalar.trim().toLowerCase();
		if (["1", "true", "on", "active"].includes(normalized)) return true;
		if (["0", "false", "off", "inactive"].includes(normalized)) return false;
	}
	return null;
};

const asObject = (value) => (isPlainObject(value) ? value : {});

const cleanString = (value, fallback = "") => {
	if (typeof value === "string") {
		const trimmed = value.trim();
		return trimmed || fallback;
	}
	if (value === undefined || value === null) return fallback;
	const coerced = String(value).trim();
	return coerced || fallback;
};

const cleanLowerString = (value, fallback = "") =>
	cleanString(value, fallback).toLowerCase();

const escapeRegex = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const parseDelimitedQueryValues = (...values) => {
	const rawValues = values.flatMap((value) => (Array.isArray(value) ? value : [value]));
	const parsed = [];

	for (const rawValue of rawValues) {
		const value = cleanString(rawValue);
		if (!value) continue;
		parsed.push(...value.split(",").map((item) => cleanString(item)).filter(Boolean));
	}

	return [...new Set(parsed)];
};

const getClientIp = (req) => {
	const forwarded = req.headers["x-forwarded-for"];
	if (typeof forwarded === "string" && forwarded.trim()) {
		return forwarded.split(",")[0].trim();
	}
	return req.socket?.remoteAddress || "unknown";
};

const normalizeActivitySeverity = (value, eventType = "system") => {
	const severity = cleanLowerString(value);
	if (ACTIVITY_SEVERITIES.has(severity)) {
		return severity === "alert" ? "danger" : severity;
	}
	if (eventType === "threshold" || eventType === "security") return "warning";
	if (eventType === "control") return "success";
	return "info";
};

const activityPriority = (severity) => ACTIVITY_SEVERITY_PRIORITY[severity] ?? 0;

const activityLogDocToPayload = (doc = {}) => {
	const createdAt = toValidDate(doc.created_at) || new Date();
	return {
		id: doc.log_id || String(doc._id || ""),
		log_id: doc.log_id || String(doc._id || ""),
		user_id: doc.user_id || "",
		user_name: doc.user_name || "",
		env_id: doc.env_id || DEFAULT_ENV_ID,
		device_id: doc.device_id || DEFAULT_DEVICE_ID,
		target_id: doc.target_id || "",
		device_name: doc.device_name || "",
		room: doc.room || "",
		event_type: doc.event_type || "system",
		trigger_source: doc.trigger_source || "system",
		severity: doc.severity || doc.status || "info",
		status: doc.status || doc.severity || "info",
		priority: doc.priority ?? activityPriority(doc.severity || doc.status),
		action: doc.action || "",
		message: doc.message || doc.response_text || "",
		response_text: doc.response_text || doc.message || "",
		actor_type: doc.actor_type || "",
		actor_name: doc.actor_name || doc.user_name || "",
		old_value: doc.old_value ?? null,
		new_value: doc.new_value ?? null,
		details: doc.details || {},
		metadata: doc.metadata || {},
		show_on_sidebar: doc.show_on_sidebar !== false,
		created_at: createdAt.toISOString(),
		createdAt: createdAt.toISOString(),
		created_at_vn: toVnTimestamp(createdAt),
		timestamp: createdAt.getTime(),
	};
};

const resolveUserName = async (userId, fallback = "") => {
	if (!userId || userId === "system" || userId === "anonymous") {
		return fallback;
	}
	try {
		const user = await usersCollection?.findOne({ user_id: userId });
		return user?.full_name || fallback;
	} catch {
		return fallback;
	}
};

const buildActivityLogDocument = async (payload = {}, req = null) => {
	const eventType = cleanLowerString(payload.event_type ?? payload.eventType, "system");
	const triggerSource = cleanLowerString(
		payload.trigger_source ?? payload.triggerSource,
		"system",
	);
	const severity = normalizeActivitySeverity(payload.severity ?? payload.status, eventType);
	const createdAt =
		toValidDate(payload.created_at ?? payload.createdAt ?? payload.timestamp) ||
		new Date();
	const userId = cleanString(payload.user_id ?? payload.userId, "system");
	const fallbackActor =
		triggerSource === "hera_assistant"
			? "H.E.R.A Assistant"
			: triggerSource === "automation"
				? "H.E.R.A Auto"
				: userId;
	const actorName =
		cleanString(
			payload.actor_name ??
				payload.actorName ??
				payload.user_name ??
				payload.userName,
		) ||
		(await resolveUserName(userId, fallbackActor)) ||
		fallbackActor;
	const targetId = cleanString(payload.target_id ?? payload.targetId, "");
	const deviceName =
		cleanString(payload.device_name ?? payload.deviceName, "") ||
		DEVICE_TARGET_LABELS[targetId] ||
		DEVICE_TARGET_LABELS[payload.device_id] ||
		DEVICE_TARGET_LABELS[DEFAULT_DEVICE_ID];
	const message = cleanString(
		payload.message ?? payload.response_text ?? payload.responseText,
		"System event recorded.",
	);
	const details = asObject(payload.details);
	const metadata = {
		...asObject(payload.metadata),
		...(req
			? {
					client_ip: getClientIp(req),
				}
			: {}),
	};

	return {
		log_id:
			cleanString(payload.log_id ?? payload.logId) ||
			`log_${createdAt.getTime()}_${Math.random().toString(36).slice(2, 10)}`,
		user_id: userId,
		user_name: cleanString(payload.user_name ?? payload.userName, actorName),
		env_id: cleanString(payload.env_id ?? payload.envId, DEFAULT_ENV_ID),
		device_id: cleanString(payload.device_id ?? payload.deviceId, DEFAULT_DEVICE_ID),
		target_id: targetId,
		device_name: deviceName,
		room: cleanString(payload.room, "Main Room"),
		event_type: eventType,
		trigger_source: triggerSource,
		severity,
		status: severity,
		priority: activityPriority(severity),
		action: cleanString(payload.action, eventType),
		message,
		response_text: message,
		actor_type: cleanLowerString(payload.actor_type ?? payload.actorType, "system"),
		actor_name: actorName,
		old_value: payload.old_value ?? payload.oldValue ?? details.old_value ?? null,
		new_value: payload.new_value ?? payload.newValue ?? details.new_value ?? null,
		details,
		metadata,
		show_on_sidebar: payload.show_on_sidebar ?? payload.showOnSidebar ?? true,
		dedupe_key: cleanString(payload.dedupe_key ?? payload.dedupeKey, ""),
		created_at: createdAt,
		updated_at: new Date(),
	};
};

const createActivityLog = async (payload, options = {}) => {
	if (!activityLogsCollection) return null;
	const doc = await buildActivityLogDocument(payload, options.req || null);

	if (doc.dedupe_key) {
		await activityLogsCollection.updateOne(
			{ dedupe_key: doc.dedupe_key },
			{ $setOnInsert: doc },
			{ upsert: true },
		);
		return activityLogsCollection.findOne({ dedupe_key: doc.dedupe_key });
	}

	await activityLogsCollection.insertOne(doc);
	return doc;
};

const safeCreateActivityLog = async (payload, options = {}) => {
	try {
		return await createActivityLog(payload, options);
	} catch (err) {
		console.error("Failed to record activity log:", err);
		return null;
	}
};

const normalizeChatRole = (value, fallback = "user") => {
	const role = cleanLowerString(value, fallback);
	return CHAT_MESSAGE_ROLES.has(role) ? role : fallback;
};

const buildChatMessageDocument = (payload = {}, fallbackRole = "user") => {
	const text = cleanString(payload.text ?? payload.content ?? payload.message);
	if (!text) return null;

	const createdAt =
		toValidDate(payload.created_at ?? payload.createdAt ?? payload.timestamp) ||
		new Date();

	return {
		message_id:
			cleanString(payload.message_id ?? payload.messageId) ||
			`msg_${createdAt.getTime()}_${Math.random().toString(36).slice(2, 10)}`,
		role: normalizeChatRole(payload.role, fallbackRole),
		text,
		created_at: createdAt,
		metadata: asObject(payload.metadata),
	};
};

const chatMessageDocToPayload = (doc = {}) => {
	const createdAt = toValidDate(doc.created_at) || new Date();
	return {
		message_id: doc.message_id || "",
		role: normalizeChatRole(doc.role),
		text: doc.text || "",
		created_at: createdAt.toISOString(),
		createdAt: createdAt.toISOString(),
		created_at_vn: toVnTimestamp(createdAt),
		timestamp: createdAt.getTime(),
		metadata: doc.metadata || {},
	};
};

const interactionSessionDocToPayload = (doc = {}) => {
	const startDate = toValidDate(doc.start_date) || new Date();
	const latestUpdate = toValidDate(doc.latest_update) || startDate;
	return {
		chat_id: doc.chat_id || "",
		user_id: doc.user_id || "",
		user_name: doc.user_name || "",
		model_name: doc.model_name || DEFAULT_CHAT_MODEL_NAME,
		env_id: doc.env_id || DEFAULT_ENV_ID,
		start_date: startDate.toISOString(),
		startDate: startDate.toISOString(),
		latest_update: latestUpdate.toISOString(),
		latestUpdate: latestUpdate.toISOString(),
		ended_at: doc.ended_at ? toValidDate(doc.ended_at)?.toISOString() || null : null,
		messages: Array.isArray(doc.messages)
			? doc.messages.map(chatMessageDocToPayload)
			: [],
	};
};

const appendInteractionMessages = async (payload = {}) => {
	if (!interactionSessionsCollection) {
		throw new Error("interaction_sessions collection is not ready");
	}

	const chatId = cleanString(payload.chat_id ?? payload.chatId);
	const userId = cleanString(payload.user_id ?? payload.userId);
	if (!chatId || !userId) {
		const error = new Error("chat_id and user_id are required");
		error.statusCode = 400;
		throw error;
	}

	const rawMessages = Array.isArray(payload.messages) ? payload.messages : [];
	const messages = rawMessages
		.map((message, index) =>
			buildChatMessageDocument(
				message,
				index % 2 === 0 ? "user" : "assistant",
			),
		)
		.filter(Boolean);

	if (messages.length === 0) {
		const error = new Error("messages are required");
		error.statusCode = 400;
		throw error;
	}

	const now = new Date();
	const latestUpdate = messages[messages.length - 1]?.created_at || now;
	const firstUserText =
		messages.find((message) => message.role === "user")?.text ||
		messages[0]?.text ||
		"";
	const sessionFields = {
		user_name: cleanString(payload.user_name ?? payload.userName),
		model_name: cleanString(
			payload.model_name ?? payload.modelName,
			DEFAULT_CHAT_MODEL_NAME,
		),
		env_id: cleanString(payload.env_id ?? payload.envId, DEFAULT_ENV_ID),
	};

	const update = {
		$set: {
			...sessionFields,
			latest_update: latestUpdate,
			ended_at: null,
		},
		$push: { messages: { $each: messages } },
	};

	const result = await interactionSessionsCollection.updateOne(
		{ chat_id: chatId, user_id: userId },
		update,
	);

	if (result.matchedCount === 0) {
		try {
			await interactionSessionsCollection.insertOne({
				chat_id: chatId,
				user_id: userId,
				...sessionFields,
				start_date: now,
				latest_update: latestUpdate,
				ended_at: null,
				input_text: firstUserText,
				messages,
			});
		} catch (err) {
			if (err?.code !== 11000) throw err;
			await interactionSessionsCollection.updateOne(
				{ chat_id: chatId, user_id: userId },
				update,
			);
		}
	}

	return interactionSessionsCollection.findOne({ chat_id: chatId, user_id: userId });
};

const buildActivityLogFilter = (query = {}) => {
	const filter = {};
	const surface = cleanLowerString(query.surface, "audit");
	const userId = cleanString(query.user_id ?? query.userId);
	const excludedLogIds = parseDelimitedQueryValues(
		query.exclude_ids,
		query.excludeIds,
		query.exclude_log_ids,
		query.excludeLogIds,
	).slice(0, MAX_ACTIVITY_EXCLUDE_IDS);

	if (userId) {
		filter.$or = [
			{ user_id: userId },
			{ user_id: "system" },
			{ user_id: "anonymous" },
		];
	}

	if (surface === "sidebar") {
		filter.show_on_sidebar = { $ne: false };
	}

	if (excludedLogIds.length > 0) {
		filter.log_id = { $nin: excludedLogIds };
	}

	for (const [queryKey, field] of [
		["event_type", "event_type"],
		["eventType", "event_type"],
		["severity", "severity"],
		["trigger_source", "trigger_source"],
		["triggerSource", "trigger_source"],
		["device_id", "device_id"],
		["deviceId", "device_id"],
		["target_id", "target_id"],
		["targetId", "target_id"],
		["room", "room"],
	]) {
		const value = cleanString(query[queryKey]);
		if (value && value !== "all") {
			filter[field] = queryKey.includes("severity") ? value.toLowerCase() : value;
		}
	}

	const fromValue = query.from ?? query.start ?? query.since;
	const toValue = query.to ?? query.end ?? query.until;
	const from = parseDateQuery(fromValue);
	const to = parseDateQuery(toValue);
	const createdAtRange = {};
	if (from) createdAtRange.$gte = from;
	if (to) createdAtRange.$lte = to;
	if (Object.keys(createdAtRange).length) {
		filter.created_at = createdAtRange;
	}

	const search = cleanString(query.search ?? query.q);
	if (search) {
		const regex = new RegExp(escapeRegex(search), "i");
		const searchOr = [
			{ message: regex },
			{ response_text: regex },
			{ device_name: regex },
			{ actor_name: regex },
		];
		if (filter.$or) {
			filter.$and = [{ $or: filter.$or }, { $or: searchOr }];
			delete filter.$or;
		} else {
			filter.$or = searchOr;
		}
	}

	return filter;
};

const createThresholdLogsFromTelemetry = async (telemetry, { userId, deviceId }) => {
	if (!activityLogsCollection || !telemetry) return [];

	const sensors = telemetry.sensors || {};
	const temperature = sensors.dht20?.temperature ?? sensors.temperature;
	const humidity = sensors.dht20?.humidity ?? sensors.humidity;
	const light = sensors.light?.value ?? sensors.light;
	const gasValue = sensors.gas?.value ?? sensors.gas;
	const gasDetected = sensors.gas?.detected ?? sensors.gas_detected;
	const temperatureValue = toNullableNumber(temperature);
	const humidityValue = toNullableNumber(humidity);
	const lightValue = toNullableNumber(light);
	const gasNumericValue = toNullableNumber(gasValue);
	const timestamp = Number(telemetry.timestamp) || Date.now();
	const bucket = Math.floor(timestamp / ACTIVITY_LOG_DEDUPE_WINDOW_MS);
	const logUserId = userId || telemetry.metadata?.user_id || "system";
	const thresholds = sensorThresholdConfig;
	const logs = [];

	const pushThreshold = ({
		sensor,
		value,
		threshold,
		unit,
		severity,
		message,
		comparison,
	}) => {
		if (value === null || value === undefined) return;
		logs.push(
			safeCreateActivityLog({
				user_id: logUserId,
				env_id: telemetry.metadata?.env_id || DEFAULT_ENV_ID,
				device_id: deviceId || telemetry.metadata?.device_id || DEFAULT_DEVICE_ID,
				target_id: sensor,
				device_name: DEVICE_TARGET_LABELS[deviceId] || "Yolo Uno",
				room: "Living Room",
				event_type: "threshold",
				trigger_source: "automation",
				severity,
				action: "Threshold Exceeded",
				message,
				actor_type: "automation",
				actor_name: "H.E.R.A Auto",
				new_value: value,
				details: { sensor, value, threshold, unit, comparison },
				show_on_sidebar: true,
				dedupe_key: `${logUserId}:${deviceId || DEFAULT_DEVICE_ID}:threshold:${sensor}:${severity}:${bucket}`,
				created_at: new Date(timestamp),
			}),
		);
	};

	if (temperatureValue !== null && thresholds.temperatureMax !== null && temperatureValue > thresholds.temperatureMax) {
		const dangerThreshold = thresholds.temperatureDangerMax ?? thresholds.temperatureMax;
		const severity = temperatureValue >= dangerThreshold ? "danger" : "warning";
		const threshold = severity === "danger" ? dangerThreshold : thresholds.temperatureMax;
		pushThreshold({
			sensor: "temperature",
			value: temperatureValue,
			threshold,
			unit: "C",
			severity,
			comparison: "above",
			message: `Temperature in Living Room exceeded ${threshold}C (${temperatureValue.toFixed(1)}C).`,
		});
	}

	if (temperatureValue !== null && thresholds.temperatureMin !== null && temperatureValue < thresholds.temperatureMin) {
		const dangerThreshold = thresholds.temperatureDangerMin ?? thresholds.temperatureMin;
		const severity = temperatureValue <= dangerThreshold ? "danger" : "warning";
		const threshold = severity === "danger" ? dangerThreshold : thresholds.temperatureMin;
		pushThreshold({
			sensor: "temperature",
			value: temperatureValue,
			threshold,
			unit: "C",
			severity,
			comparison: "below",
			message: `Temperature in Living Room dropped below ${threshold}C (${temperatureValue.toFixed(1)}C).`,
		});
	}

	if (humidityValue !== null && thresholds.humidityMax !== null && humidityValue > thresholds.humidityMax) {
		pushThreshold({
			sensor: "humidity",
			value: humidityValue,
			threshold: thresholds.humidityMax,
			unit: "%",
			severity: "warning",
			comparison: "above",
			message: `Humidity in Living Room exceeded ${thresholds.humidityMax}% (${humidityValue.toFixed(1)}%).`,
		});
	}

	if (humidityValue !== null && thresholds.humidityMin !== null && humidityValue < thresholds.humidityMin) {
		pushThreshold({
			sensor: "humidity",
			value: humidityValue,
			threshold: thresholds.humidityMin,
			unit: "%",
			severity: "warning",
			comparison: "below",
			message: `Humidity in Living Room dropped below ${thresholds.humidityMin}% (${humidityValue.toFixed(1)}%).`,
		});
	}

	if (lightValue !== null && thresholds.lightMax !== null && lightValue > thresholds.lightMax) {
		pushThreshold({
			sensor: "light",
			value: lightValue,
			threshold: thresholds.lightMax,
			unit: "lux",
			severity: "warning",
			comparison: "above",
			message: `Ambient light in Living Room exceeded ${thresholds.lightMax} lux (${lightValue.toFixed(0)} lux).`,
		});
	}

	if (lightValue !== null && thresholds.lightMin !== null && lightValue < thresholds.lightMin) {
		pushThreshold({
			sensor: "light",
			value: lightValue,
			threshold: thresholds.lightMin,
			unit: "lux",
			severity: "warning",
			comparison: "below",
			message: `Ambient light in Living Room dropped below ${thresholds.lightMin} lux (${lightValue.toFixed(0)} lux).`,
		});
	}

	if (gasDetected === true || (gasNumericValue !== null && gasNumericValue >= thresholds.gasMax)) {
		const value = gasDetected === true ? "detected" : gasNumericValue;
		pushThreshold({
			sensor: "gas",
			value,
			threshold: thresholds.gasMax,
			unit: "ppm",
			severity: "danger",
			comparison: "above",
			message:
				gasDetected === true
					? "Gas leak signal detected in Living Room."
					: `Gas level in Living Room reached ${gasNumericValue.toFixed(0)} ppm.`,
		});
	}

	return Promise.all(logs);
};

const normalizeTelemetrySensors = (doc = {}) => {
	const sensors = asObject(doc.sensors);
	const dht20 = asObject(firstPresent(sensors.dht20, sensors.dht));
	const light = asObject(sensors.light);
	const gas = asObject(sensors.gas);
	const gasValue = toNullableNumber(
		firstPresent(
			gas.value,
			sensors.gas,
			sensors.gas_ppm,
			doc.gas_ppm,
			doc.gasPpm,
			doc.gas,
		),
	);

	return {
		dht20: {
			...dht20,
			temperature: toNullableNumber(
				firstPresent(sensors.temperature, dht20.temperature, doc.temperature, doc.temp),
			),
			humidity: toNullableNumber(
				firstPresent(sensors.humidity, dht20.humidity, doc.humidity, doc.humi),
			),
		},
		light: {
			...light,
			value: toNullableNumber(firstPresent(light.value, sensors.light, doc.light, doc.lux)),
		},
		gas: {
			...gas,
			value: gasValue,
			detected: toNullableBoolean(
				firstPresent(
					gas.detected,
					gas.gas_detected,
					sensors.gas_detected,
					doc.gas_detected,
					doc.gasDetected,
				),
			),
		},
	};
};

const normalizeTelemetryDevices = (doc = {}) => {
	const devices = asObject(doc.devices);
	const led = asObject(devices.led);
	const neoLed = asObject(firstPresent(devices.neo_led, devices.neo));
	const ws2812 = asObject(devices.ws2812);
	const relay = asObject(devices.relay);
	const miniFan = asObject(firstPresent(devices.mini_fan, devices.fan));

	return {
		led: {
			...led,
			status: toNullableBoolean(
				firstPresent(devices.led_status, led.status, doc.led_status, doc.led_state),
			),
		},
		neo_led: {
			...neoLed,
			status: toNullableBoolean(
				firstPresent(
					devices.neo_led_status,
					neoLed.status,
					doc.neo_led_status,
					doc.neo_led_state,
				),
			),
			brightness: toNullableNumber(
				firstPresent(devices.strip_brightness, neoLed.brightness),
			),
		},
		ws2812: {
			...ws2812,
			status: toNullableBoolean(
				firstPresent(devices.ws2812_status, ws2812.status, doc.ws2812_status),
			),
			brightness: toNullableNumber(
				firstPresent(devices.ws2812_brightness, ws2812.brightness),
			),
		},
		relay: {
			...relay,
			status: toNullableBoolean(
				firstPresent(devices.relay_status, relay.status, doc.relay_status),
			),
		},
		mini_fan: {
			...miniFan,
			status: toNullableBoolean(
				firstPresent(devices.mini_fan_status, miniFan.status, doc.mini_fan_status),
			),
			speed: toNullableNumber(firstPresent(devices.fan_speed, miniFan.speed)),
		},
	};
};

const normalizeTelemetryNetwork = (doc = {}) => {
	const network = asObject(doc.network);

	return {
		wifi_connected: toNullableBoolean(
			firstPresent(network.wifi_connected, doc.wifi_connected),
		),
		wifi_rssi: toNullableNumber(firstPresent(network.wifi_rssi, doc.wifi_rssi)),
		wifi_ip: firstPresent(network.wifi_ip, doc.wifi_ip) ?? null,
		mqtt_connected: toNullableBoolean(
			firstPresent(network.mqtt_connected, doc.mqtt_connected),
		),
		uptime_ms: toNullableNumber(firstPresent(network.uptime_ms, doc.uptime_ms)),
	};
};

const telemetryDocToPayload = (doc, index = 0) => {
	const recordedAt = toValidDate(doc.recorded_at) || new Date();
	const chartRecordedAt =
		toValidDate(doc.chart_recorded_at) ||
		floorToTelemetryBucket(recordedAt) ||
		recordedAt;
	const sensors = normalizeTelemetrySensors(doc);
	const devices = normalizeTelemetryDevices(doc);
	const network = normalizeTelemetryNetwork(doc);

	return {
		id: index + 1,
		timestamp: recordedAt.getTime(),
		recorded_at: recordedAt.toISOString(),
		time: recordedAt.toLocaleTimeString("vi-VN", {
			hour: "2-digit",
			minute: "2-digit",
			second: "2-digit",
		}),
		chart_timestamp: chartRecordedAt.getTime(),
		chart_recorded_at: chartRecordedAt.toISOString(),
		chart_time: chartRecordedAt.toLocaleTimeString("vi-VN", {
			hour: "2-digit",
			minute: "2-digit",
			second: "2-digit",
		}),
		sensors,
		devices,
		network,
		runtime: doc.runtime || {},
		last_seen_at: doc.last_seen_at || null,
		source_topic: doc.source_topic || null,
		metadata: doc.metadata || {},
	};
};

const telemetryFilter = (deviceId, userId, includeUser = true, range = {}) => {
	const filter = { "metadata.device_id": deviceId };
	if (includeUser && userId) {
		filter["metadata.user_id"] = userId;
	}
	const recordedAtRange = {};
	if (range.from) recordedAtRange.$gte = range.from;
	if (range.to) recordedAtRange.$lte = range.to;
	if (Object.keys(recordedAtRange).length) {
		filter.recorded_at = recordedAtRange;
	}
	return filter;
};

const findTelemetryDocs = async ({ deviceId, userId, limit, from = null, to = null }) => {
	const range = { from, to };
	let docs = await collection
		.find(telemetryFilter(deviceId, userId, true, range))
		.sort({ recorded_at: -1 })
		.limit(limit)
		.toArray();

	if (docs.length === 0) {
		docs = await collection
			.find(telemetryFilter(deviceId, userId, false, range))
			.sort({ recorded_at: -1 })
			.limit(limit)
			.toArray();
	}

	return docs;
};

const findLatestTelemetryDoc = async ({ deviceId, userId }) => {
	let doc = await collection.findOne(telemetryFilter(deviceId, userId, true), {
		sort: { recorded_at: -1 },
	});

	if (!doc) {
		doc = await collection.findOne(telemetryFilter(deviceId, userId, false), {
			sort: { recorded_at: -1 },
		});
	}

	return doc;
};

const toLegacyEnvShapedPayload = (envValues) => {
	const provider =
		envValues.LLM_PROVIDER === "ollama" || envValues.LLM_PROVIDER === "openrouter"
			? envValues.LLM_PROVIDER
			: DEFAULT_MODEL_SETTINGS.provider;
	const payload = buildModelSettingsPayload({ provider });
	for (const targetProvider of ["ollama", "openrouter"]) {
		const mapping = ENV_TO_PAYLOAD_MAPPING[targetProvider];
		for (const [field, envKey] of Object.entries(mapping)) {
			if (field === "provider") continue;
			if (typeof envValues[envKey] === "string" && envValues[envKey].trim()) {
				payload.models[targetProvider][field] = envValues[envKey].trim();
			}
		}
	}
	return payload;
};

const sanitizeModelSettingsPayload = (payload) => {
	const provider = payload?.provider;
	if (provider !== "ollama" && provider !== "openrouter") {
		throw new Error("provider must be either 'ollama' or 'openrouter'");
	}

	const result = { provider, models: { ollama: {}, openrouter: {} } };
	for (const targetProvider of ["ollama", "openrouter"]) {
		const incoming = payload?.models?.[targetProvider] || {};
		for (const field of Object.keys(ENV_TO_PAYLOAD_MAPPING[targetProvider])) {
			const value = incoming[field];
			if (typeof value === "string") {
				result.models[targetProvider][field] = value.trim();
			}
		}
	}
	return result;
};

const getModelSettings = async () => {
	let doc = await modelSettingsCollection.findOne({ _id: MODEL_SETTINGS_DOC_ID });
	if (doc) {
		const payload = buildModelSettingsPayload(doc);
		return {
			...payload,
			createdAt: doc.created_at || null,
			updatedAt: doc.updated_at || null,
			createdAtVn: toVnTimestamp(doc.created_at),
			updatedAtVn: toVnTimestamp(doc.updated_at),
		};
	}

	try {
		const envContent = await fs.readFile(ENV_PATH, "utf8");
		const envValues = parseEnv(envContent);
		const initial = toLegacyEnvShapedPayload(envValues);
		const now = new Date();
		await modelSettingsCollection.updateOne(
			{ _id: MODEL_SETTINGS_DOC_ID },
			{
				$set: {
					_id: MODEL_SETTINGS_DOC_ID,
					...initial,
					created_at: now,
					updated_at: now,
				},
			},
			{ upsert: true },
		);
		return {
			...initial,
			createdAt: now,
			updatedAt: now,
			createdAtVn: toVnTimestamp(now),
			updatedAtVn: toVnTimestamp(now),
		};
	} catch {
		const payload = buildModelSettingsPayload();
		return {
			...payload,
			createdAt: null,
			updatedAt: null,
			createdAtVn: "",
			updatedAtVn: "",
		};
	}
};

async function start() {
	await loadSensorThresholdConfig();
	await client.connect();
	const db = client.db(MONGODB_DB);
	collection = db.collection("telemetry_points");
	usersCollection = db.collection("users");
	modelSettingsCollection = db.collection("model_settings");
	devicesCollection = db.collection("devices"); // Init thiết bị
	activityLogsCollection = db.collection("activity_logs");
	interactionSessionsCollection = db.collection("interaction_sessions");

	await Promise.all([
		interactionSessionsCollection.createIndex({ chat_id: 1, user_id: 1 }),
		interactionSessionsCollection.createIndex({ user_id: 1 }),
		interactionSessionsCollection.createIndex({ env_id: 1 }),
		interactionSessionsCollection.createIndex({ user_id: 1, latest_update: -1 }),
		activityLogsCollection.createIndex({ created_at: -1 }),
		activityLogsCollection.createIndex({ user_id: 1, created_at: -1 }),
		activityLogsCollection.createIndex({ event_type: 1, created_at: -1 }),
		activityLogsCollection.createIndex({ severity: 1, created_at: -1 }),
		activityLogsCollection.createIndex({ trigger_source: 1, created_at: -1 }),
		activityLogsCollection.createIndex({ show_on_sidebar: 1, priority: -1, created_at: -1 }),
		activityLogsCollection.createIndex(
			{ dedupe_key: 1 },
			{ unique: true, partialFilterExpression: { dedupe_key: { $exists: true, $gt: "" } } },
		),
	]);

	app.get("/api/activity-logs", async (req, res) => {
		try {
			const surface = cleanLowerString(req.query.surface, "audit");
			const page = parseActivityPage(req.query.page);
			const pageSize = parseActivityLimit(req.query.page_size ?? req.query.pageSize ?? req.query.limit);
			const skip = surface === "sidebar" ? 0 : (page - 1) * pageSize;
			const filter = buildActivityLogFilter(req.query);
			const sort =
				surface === "sidebar"
					? { created_at: -1, priority: -1 }
					: { created_at: -1 };

			const [docs, total] = await Promise.all([
				activityLogsCollection
					.find(filter, { projection: { _id: 0 } })
					.sort(sort)
					.skip(skip)
					.limit(pageSize)
					.toArray(),
				activityLogsCollection.countDocuments(filter),
			]);

			res.json({
				items: docs.map(activityLogDocToPayload),
				total,
				page,
				pageSize,
			});
		} catch (err) {
			console.error(err);
			res.status(500).json({ error: "Failed to fetch activity logs" });
		}
	});

	app.post("/api/activity-logs", async (req, res) => {
		try {
			const payload = req.body || {};
			if (!payload.message && !payload.response_text && !payload.responseText) {
				return res.status(400).json({ error: "message is required" });
			}

			const doc = await createActivityLog(payload, { req });
			res.status(201).json({
				success: true,
				log: activityLogDocToPayload(doc),
			});
		} catch (err) {
			if (err?.code === 11000) {
				return res.status(409).json({ error: "Activity log already exists" });
			}
			console.error(err);
			res.status(500).json({ error: "Failed to create activity log" });
		}
	});

	app.get("/api/interaction-sessions/:chatId", async (req, res) => {
		try {
			const chatId = cleanString(req.params.chatId);
			const userId = cleanString(req.query.user_id ?? req.query.userId);
			if (!chatId || !userId) {
				return res.status(400).json({ error: "chat_id and user_id are required" });
			}

			const doc = await interactionSessionsCollection.findOne(
				{ chat_id: chatId, user_id: userId },
				{ projection: { _id: 0 } },
			);

			if (!doc) {
				return res.json({ session: null, messages: [] });
			}

			const session = interactionSessionDocToPayload(doc);
			res.json({ session, messages: session.messages });
		} catch (err) {
			console.error(err);
			res.status(500).json({ error: "Failed to fetch interaction session" });
		}
	});

	app.post("/api/interaction-sessions/messages", async (req, res) => {
		try {
			const doc = await appendInteractionMessages(req.body || {});
			const session = interactionSessionDocToPayload(doc);
			res.status(201).json({
				success: true,
				session,
				messages: session.messages,
			});
		} catch (err) {
			console.error(err);
			res
				.status(err.statusCode || 500)
				.json({ error: err.message || "Failed to save interaction session" });
		}
	});

	app.post("/api/auth/login", async (req, res) => {
		try {
			const { email, password } = req.body;

			if (!email || !password) {
				return res.status(400).json({ error: "Email and password are required" });
			}

			const user = await usersCollection.findOne({
				email,
				password_hash: password,
			});

			if (!user) {
				await safeCreateActivityLog(
					{
						user_id: "anonymous",
						env_id: DEFAULT_ENV_ID,
						device_id: DEFAULT_DEVICE_ID,
						target_id: "system",
						device_name: "System",
						room: "Security",
						event_type: "security",
						trigger_source: "auth",
						severity: "warning",
						action: "Login Failed",
						message: `Login failed for ${email}.`,
						actor_type: "unknown",
						actor_name: "Unknown IP",
						details: {
							email,
							reason: "invalid_credentials",
							ip: getClientIp(req),
						},
						show_on_sidebar: true,
					},
					{ req },
				);
				return res.status(401).json({ error: "Invalid email or password" });
			}

			await safeCreateActivityLog(
				{
					user_id: user.user_id,
					user_name: user.full_name,
					env_id: DEFAULT_ENV_ID,
					device_id: DEFAULT_DEVICE_ID,
					target_id: "system",
					device_name: "System",
					room: "Security",
					event_type: "security",
					trigger_source: "auth",
					severity: "info",
					action: "Login Success",
					message: `${user.full_name} signed in.`,
					actor_type: "user",
					actor_name: user.full_name,
					details: {
						email,
						ip: getClientIp(req),
					},
					show_on_sidebar: false,
				},
				{ req },
			);

			return res.json({
				success: true,
				user: {
					user_id: user.user_id,
					full_name: user.full_name,
					email: user.email,
				},
			});
		} catch (err) {
			console.error(err);
			res.status(500).json({ error: "Failed to login" });
		}
	});

    // API mới: Gán thiết bị cho user đang hoạt động
    app.post("/api/device/claim", async (req, res) => {
        try {
            const { device_id, user_id } = req.body;
            if (!device_id || !user_id) {
                return res.status(400).json({ error: "device_id and user_id are required" });
            }
            await devicesCollection.updateOne(
                { device_id: device_id },
                { $set: { current_user_id: user_id } },
                { upsert: true }
            );
			await safeCreateActivityLog({
				user_id,
				env_id: DEFAULT_ENV_ID,
				device_id,
				target_id: device_id,
				device_name: DEVICE_TARGET_LABELS[device_id] || device_id,
				room: "Main Room",
				event_type: "system",
				trigger_source: "web_dashboard",
				severity: "info",
				action: "Device Claimed",
				message: `Device ${device_id} is now assigned to ${user_id}.`,
				actor_type: "user",
				details: { device_id, user_id },
				show_on_sidebar: false,
			});
            res.json({ success: true, message: `Device ${device_id} is now claimed by ${user_id}` });
        } catch (err) {
            console.error(err);
            res.status(500).json({ error: "Failed to claim device" });
        }
    });

	app.get("/api/telemetry", async (req, res) => {
		try {
			const deviceId = req.query.device_id || "device_0001";
            const userId = req.query.user_id; // Bắt buộc nhận user_id
			const fromValue = req.query.from ?? req.query.start ?? req.query.since;
			const toValue = req.query.to ?? req.query.end ?? req.query.until;
			const from = parseDateQuery(fromValue);
			const to = parseDateQuery(toValue);
			const hasFrom = hasQueryValue(fromValue);
			const hasTo = hasQueryValue(toValue);
			const limit = parseTelemetryLimit(req.query.limit, hasFrom || hasTo ? 10000 : 300);

            if (!userId) {
                return res.status(400).json({ error: "user_id parameter is required to fetch personalized data" });
            }

			if ((hasFrom && !from) || (hasTo && !to)) {
				return res.status(400).json({ error: "Invalid telemetry time range" });
			}

			if (from && to && from.getTime() > to.getTime()) {
				return res.status(400).json({ error: "from must be before to" });
			}

			const docs = await findTelemetryDocs({ deviceId, userId, limit, from, to });

			const data = docs.reverse().map(telemetryDocToPayload);

			res.json(data);
		} catch (err) {
			console.error(err);
			res.status(500).json({ error: "Failed to fetch telemetry" });
		}
	});

	app.get("/api/sensors/latest", async (req, res) => {
		try {
			const deviceId = req.query.device_id || "device_0001";
            const userId = req.query.user_id;

            if (!userId) {
                return res.status(400).json({ error: "user_id parameter is required" });
            }

			const docs = await findTelemetryDocs({ deviceId, userId, limit: 1 });

			if (docs.length === 0) {
				return res.status(404).json({ error: "No sensor data found for this user" });
			}

			const payload = telemetryDocToPayload(docs[0]);
			await createThresholdLogsFromTelemetry(payload, { userId, deviceId });
			res.json(payload);
		} catch (err) {
			console.error(err);
			res.status(500).json({ error: "Failed to fetch latest sensor data" });
		}
	});

	app.get("/api/sensors/stream", async (req, res) => {
		const deviceId = req.query.device_id || "device_0001";
		const userId = req.query.user_id;

		if (!userId) {
			return res.status(400).json({ error: "user_id parameter is required" });
		}

		res.setHeader("Content-Type", "text/event-stream");
		res.setHeader("Cache-Control", "no-cache");
		res.setHeader("Connection", "keep-alive");
		res.flushHeaders?.();

		let lastTimestamp = 0;

		const sendLatest = async () => {
			try {
				const doc = await findLatestTelemetryDoc({ deviceId, userId });

				if (!doc) {
					return;
				}

				const payload = telemetryDocToPayload(doc);
				if (payload.timestamp <= lastTimestamp) {
					return;
				}

				lastTimestamp = payload.timestamp;
				await createThresholdLogsFromTelemetry(payload, { userId, deviceId });
				res.write(`event: telemetry\n`);
				res.write(`data: ${JSON.stringify(payload)}\n\n`);
			} catch (err) {
				res.write(`event: error\n`);
				res.write(`data: ${JSON.stringify({ error: "stream_read_failed" })}\n\n`);
			}
		};

		await sendLatest();
		const interval = setInterval(sendLatest, 1000);
		req.on("close", () => {
			clearInterval(interval);
			res.end();
		});
	});

	app.get("/api/settings/models", async (_req, res) => {
		try {
			const settings = await getModelSettings();
			res.json(settings);
		} catch (err) {
			console.error(err);
			res.status(500).json({ error: "Failed to load model settings" });
		}
	});

	app.put("/api/settings/models", async (req, res) => {
		try {
			const before = await getModelSettings();
			const sanitized = sanitizeModelSettingsPayload(req.body || {});
			const mergedPayload = buildModelSettingsPayload(sanitized);
			await modelSettingsCollection.updateOne(
				{ _id: MODEL_SETTINGS_DOC_ID },
				{
					$set: {
						_id: MODEL_SETTINGS_DOC_ID,
						...mergedPayload,
						updated_at: new Date(),
					},
					$setOnInsert: { created_at: new Date() },
				},
				{ upsert: true },
			);
			const providerChanged = before.provider !== mergedPayload.provider;
			const color = providerChanged ? ANSI.yellow : ANSI.green;
			const providerText = mergedPayload.provider;
			console.log(
				`${color}[ModelSettings] Switched to provider: ${providerText}${ANSI.reset}`,
			);
			await safeCreateActivityLog({
				user_id: "system",
				env_id: DEFAULT_ENV_ID,
				device_id: DEFAULT_DEVICE_ID,
				target_id: "model_settings",
				device_name: "Model Settings",
				room: "System",
				event_type: "system",
				trigger_source: "web_dashboard",
				severity: providerChanged ? "warning" : "info",
				action: providerChanged ? "Provider Changed" : "Model Settings Updated",
				message: providerChanged
					? `LLM provider changed from ${before.provider} to ${mergedPayload.provider}.`
					: "Model settings were updated.",
				actor_type: "user",
				details: {
					before_provider: before.provider,
					after_provider: mergedPayload.provider,
				},
				show_on_sidebar: providerChanged,
			});
			res.json({
				success: true,
				settings: await getModelSettings(),
			});
		} catch (err) {
			console.error(err);
			console.error(`${ANSI.red}[ModelSettings] Save failed.${ANSI.reset}`);
			res.status(400).json({
				error: err.message || "Failed to save model settings",
			});
		}
	});

	app.listen(3001, () => {
		console.log("API running at http://localhost:3001");
	});
}

start().catch(console.error);
