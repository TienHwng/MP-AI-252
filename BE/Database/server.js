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
	await client.connect();
	const db = client.db(MONGODB_DB);
	collection = db.collection("telemetry_points");
	usersCollection = db.collection("users");
	modelSettingsCollection = db.collection("model_settings");
	devicesCollection = db.collection("devices"); // Init thiết bị

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
				return res.status(401).json({ error: "Invalid email or password" });
			}

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

			res.json(telemetryDocToPayload(docs[0]));
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
