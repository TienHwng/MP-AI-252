const express = require("express");
const cors = require("cors");
const { MongoClient } = require("mongodb");

const app = express();
app.use(cors());
app.use(express.json());

const client = new MongoClient("mongodb://localhost:27017");
let collection;

async function start() {
	await client.connect();
	const db = client.db("HERA");
	collection = db.collection("telemetry_points");

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
			
			// Chỉ lấy 1 document mới nhất (limit: 1)
			const docs = await collection
				.find({ "metadata.device_id": deviceId })
				.sort({ recorded_at: -1 })
				.limit(1)
				.toArray();

			if (docs.length === 0) {
				return res.status(404).json({ error: "No sensor data found" });
			}

			// Trả về thẳng object đầu tiên (không nằm trong array)
			res.json(docs[0]);
		} catch (err) {
			console.error(err);
			res.status(500).json({ error: "Failed to fetch latest sensor data" });
		}
	});

	app.listen(3001, () => {
		console.log("API running at http://localhost:3001");
	});

	app.post("/api/control/led", async (req, res) => {
	try {
		const enabled = Boolean(req.body.enabled);
		mqttManager.send_rpc_command("setValueLedBlinky", enabled);
		res.json({ success: true, enabled });
	} catch (err) {
		console.error(err);
		res.status(500).json({ error: "Failed to control LED light" });
	}
});

app.post("/api/control/neon", async (req, res) => {
	try {
		const enabled = Boolean(req.body.enabled);
		mqttManager.send_rpc_command("setValueNeoLed", enabled);
		res.json({ success: true, enabled });
	} catch (err) {
		console.error(err);
		res.status(500).json({ error: "Failed to control neon light" });
	}
});
}

start().catch(console.error);
