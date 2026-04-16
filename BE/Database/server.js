const express = require("express");
const cors = require("cors");
const { MongoClient } = require("mongodb");
const fs = require("fs/promises");
const path = require("path");

const app = express();
app.use(cors());
app.use(express.json());

const client = new MongoClient("mongodb://localhost:27017");
let collection;
let usersCollection;
let modelSettingsCollection;
const ENV_PATH = path.resolve(__dirname, "../../.env");
const MODEL_SETTINGS_DOC_ID = "hera_model_settings";
const ANSI = {
	reset: "\x1b[0m",
	green: "\x1b[32m",
	yellow: "\x1b[33m",
	red: "\x1b[31m",
};
const VN_TIMEZONE = "Asia/Ho_Chi_Minh";

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
	const db = client.db("HERA");
	collection = db.collection("telemetry_points");
	usersCollection = db.collection("users");
	modelSettingsCollection = db.collection("model_settings");

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

	app.get("/api/telemetry", async (req, res) => {
		try {
			const deviceId = req.query.device_id || "device_0001";
			const limit = Math.min(Number(req.query.limit || 300), 5000);

			const docs = await collection
				.find({ "metadata.device_id": deviceId })
				.sort({ recorded_at: -1 })
				.limit(limit)
				.toArray();

			const data = docs.reverse().map((doc, index) => {
				const recordedAt = new Date(doc.recorded_at);

				return {
					id: index + 1,
					timestamp: recordedAt.getTime(),
					recorded_at: recordedAt.toISOString(),
					time: recordedAt.toLocaleTimeString("vi-VN", {
						hour: "2-digit",
						minute: "2-digit",
						second: "2-digit",
					}),
					temp: doc.sensors?.temperature ?? null,
					humidity: doc.sensors?.humidity ?? null,
					light: doc.sensors?.light ?? null,
				};
			});

			res.json(data);
		} catch (err) {
			console.error(err);
			res.status(500).json({ error: "Failed to fetch telemetry" });
		}
	});

	app.get("/api/sensors/latest", async (req, res) => {
		try {
			const deviceId = req.query.device_id || "device_0001";

			const docs = await collection
				.find({ "metadata.device_id": deviceId })
				.sort({ recorded_at: -1 })
				.limit(1)
				.toArray();

			if (docs.length === 0) {
				return res.status(404).json({ error: "No sensor data found" });
			}

			res.json(docs[0]);
		} catch (err) {
			console.error(err);
			res.status(500).json({ error: "Failed to fetch latest sensor data" });
		}
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
