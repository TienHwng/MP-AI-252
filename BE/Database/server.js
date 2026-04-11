const express = require("express");
const cors = require("cors");
const { MongoClient } = require("mongodb");

const app = express();
app.use(cors());
app.use(express.json());

const client = new MongoClient("mongodb://localhost:27017");
let collection;
let usersCollection;

async function start() {
	await client.connect();
	const db = client.db("HERA");
	collection = db.collection("telemetry_points");
	usersCollection = db.collection("users");

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

	app.listen(3001, () => {
		console.log("API running at http://localhost:3001");
	});
}

start().catch(console.error);