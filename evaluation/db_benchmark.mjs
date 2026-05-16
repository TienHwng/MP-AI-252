// Benchmark MongoDB insert throughput and the 24h chart query used by frontend Analytics.
//
// Example:
//   node docs/evaluation/db_benchmark.mjs --count 17280 --api http://localhost:3001

import { MongoClient } from 'mongodb';
import { performance } from 'node:perf_hooks';
import fs from 'node:fs/promises';
import path from 'node:path';

const args = new Map();
for (let i = 2; i < process.argv.length; i += 2) {
	args.set(process.argv[i], process.argv[i + 1]);
}

const mongoUri = args.get('--mongo') || process.env.MONGODB_URI || 'mongodb://localhost:27017';
const dbName = args.get('--db') || process.env.MONGODB_DB || 'HERA';
const collectionName = args.get('--collection') || process.env.MONGODB_COLLECTION || 'telemetry_points';
const apiBase = args.get('--api') || 'http://localhost:3001';
const count = Number(args.get('--count') || 17280); // 24h at 5s interval
const batchSize = Number(args.get('--batch-size') || 500);
const userId = args.get('--user-id') || 'eval_user';
const deviceId = args.get('--device-id') || 'device_0001';
const outDir = args.get('--out-dir') || 'docs/evaluation/results';

function telemetryDoc(index, startMs) {
	const recordedAt = new Date(startMs + index * 5000);
	return {
		recorded_at: recordedAt,
		chart_recorded_at: recordedAt,
		metadata: {
			device_id: deviceId,
			env_id: 'env_0001',
			user_id: userId,
			source: 'db_benchmark',
			mode: 'sim',
		},
		network: {
			wifi_connected: true,
			wifi_rssi: -45 - (index % 20),
			wifi_ip: '192.168.1.50',
			mqtt_connected: true,
			uptime_ms: index * 5000,
		},
		devices: {
			led: { status: index % 2 === 0, brightness: index % 2 === 0 ? 512 : 0 },
			neo_led: { status: true, brightness: 128 },
			ws2812: { status: false, brightness: 0, color: '#000000' },
			relay: { status: index % 10 === 0 },
			mini_fan: { status: index % 3 === 0, speed: index % 3 === 0 ? 700 : 0 },
		},
		sensors: {
			dht20: {
				temperature: 27 + Math.sin(index / 120) * 4,
				humidity: 68 + Math.cos(index / 100) * 8,
				voltage: 3.3,
			},
			light: { value: 180 + Math.sin(index / 50) * 80, voltage: 3.3 },
			gas: { value: 120 + (index % 30), detected: false, voltage: 3.3 },
		},
	};
}

function percentile(values, pct) {
	if (!values.length) return null;
	const ordered = [...values].sort((a, b) => a - b);
	const index = Math.min(ordered.length - 1, Math.max(0, Math.round((pct / 100) * (ordered.length - 1))));
	return ordered[index];
}

await fs.mkdir(outDir, { recursive: true });
const client = new MongoClient(mongoUri);
await client.connect();
const collection = client.db(dbName).collection(collectionName);

await collection.createIndex({ 'metadata.device_id': 1, 'metadata.user_id': 1, recorded_at: -1 });

const startMs = Date.now() - 24 * 60 * 60 * 1000;
const docs = Array.from({ length: count }, (_, index) => telemetryDoc(index, startMs));

const insertStart = performance.now();
for (let index = 0; index < docs.length; index += batchSize) {
	await collection.insertMany(docs.slice(index, index + batchSize), { ordered: false });
}
const insertElapsedMs = performance.now() - insertStart;

const queryLatencies = [];
const from = new Date(startMs);
const to = new Date(startMs + count * 5000);
for (let i = 0; i < 30; i += 1) {
	const queryStart = performance.now();
	await fetch(`${apiBase}/api/telemetry?user_id=${encodeURIComponent(userId)}&device_id=${encodeURIComponent(deviceId)}&from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}&limit=${count}`);
	queryLatencies.push(performance.now() - queryStart);
}

const directQueryLatencies = [];
for (let i = 0; i < 30; i += 1) {
	const queryStart = performance.now();
	await collection
		.find({
			'metadata.device_id': deviceId,
			'metadata.user_id': userId,
			recorded_at: { $gte: from, $lte: to },
		})
		.sort({ recorded_at: -1 })
		.limit(count)
		.toArray();
	directQueryLatencies.push(performance.now() - queryStart);
}

const summary = {
	mongoUri,
	dbName,
	collectionName,
	insertedDocuments: count,
	insertElapsedMs: Number(insertElapsedMs.toFixed(3)),
	insertThroughputDocsPerSec: Number((count / (insertElapsedMs / 1000)).toFixed(2)),
	api24hQueryLatencyMs: {
		median: Number(percentile(queryLatencies, 50).toFixed(3)),
		p95: Number(percentile(queryLatencies, 95).toFixed(3)),
		min: Number(Math.min(...queryLatencies).toFixed(3)),
		max: Number(Math.max(...queryLatencies).toFixed(3)),
	},
	directMongo24hQueryLatencyMs: {
		median: Number(percentile(directQueryLatencies, 50).toFixed(3)),
		p95: Number(percentile(directQueryLatencies, 95).toFixed(3)),
		min: Number(Math.min(...directQueryLatencies).toFixed(3)),
		max: Number(Math.max(...directQueryLatencies).toFixed(3)),
	},
};

await fs.writeFile(path.join(outDir, 'db_benchmark.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
await client.close();
