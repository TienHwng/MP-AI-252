// Measure local React FloorPlan render and SSE-to-UI synchronization latency.
//
// Start FE Vite and BE/Database first:
//   cd FE/hera-dashboard; npm run dev
//   cd BE/Database; node server.js
//
// Example:
//   node docs/evaluation/web_floorplan_perf.mjs --url http://localhost:5173

import { chromium } from 'playwright';
import { MongoClient } from 'mongodb';
import { performance } from 'node:perf_hooks';
import fs from 'node:fs/promises';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

const args = new Map();
for (let i = 2; i < process.argv.length; i += 2) {
	args.set(process.argv[i], process.argv[i + 1]);
}

const url = args.get('--url') || 'http://localhost:5173';
const mongoUri = args.get('--mongo') || process.env.MONGODB_URI || 'mongodb://localhost:27017';
const dbName = args.get('--db') || process.env.MONGODB_DB || 'HERA';
const userId = args.get('--user-id') || 'eval_user';
const deviceId = args.get('--device-id') || 'device_0001';
const outDir = args.get('--out-dir') || 'docs/evaluation/results';
const runLighthouse = args.has('--lighthouse');

function percentile(values, pct) {
	if (!values.length) return null;
	const ordered = [...values].sort((a, b) => a - b);
	const index = Math.min(ordered.length - 1, Math.max(0, Math.round((pct / 100) * (ordered.length - 1))));
	return ordered[index];
}

function telemetryDoc(sequence, status) {
	const now = new Date();
	return {
		recorded_at: now,
		chart_recorded_at: now,
		metadata: {
			device_id: deviceId,
			env_id: 'env_0001',
			user_id: userId,
			source: 'web_floorplan_perf',
			mode: 'sim',
		},
		network: { wifi_connected: true, mqtt_connected: true, uptime_ms: sequence * 1000 },
		devices: {
			led: { status, brightness: status ? 512 : 0 },
			neo_led: { status: false, brightness: 0 },
			ws2812: { status: false, brightness: 0 },
			relay: { status: false },
			mini_fan: { status: false, speed: 0 },
		},
		sensors: {
			dht20: { temperature: 26 + sequence / 10, humidity: 65 },
			light: { value: 220 },
			gas: { value: 120, detected: false },
		},
	};
}

await fs.mkdir(outDir, { recursive: true });
const mongo = new MongoClient(mongoUri);
await mongo.connect();
const db = mongo.db(dbName);
await db.collection('devices').updateOne({ device_id: deviceId }, { $set: { current_user_id: userId } }, { upsert: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
await page.addInitScript(({ userIdValue }) => {
	const originalGetEntriesByType = performance.getEntriesByType.bind(performance);
	window.__heraRealGetEntriesByType = originalGetEntriesByType;
	performance.getEntriesByType = (type) => {
		const entries = originalGetEntriesByType(type);
		if (type === 'navigation') {
			return entries.map((entry) => {
				try {
					return new Proxy(entry, {
						get(target, property) {
							if (property === 'type') return 'reload';
							return Reflect.get(target, property);
						},
					});
				} catch {
					return { ...entry.toJSON?.(), type: 'reload' };
				}
			});
		}
		return entries;
	};
	window.localStorage.setItem('hera_user', JSON.stringify({
		user_id: userIdValue,
		full_name: 'Evaluation User',
		email: 'eval@example.local',
	}));
	window.localStorage.setItem('hera_active_page', 'home');
}, { userIdValue: userId });

const navigationStart = performance.now();
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForSelector('img[alt="Smart home floor plan"]', { timeout: 15000 });
const initialRenderMs = performance.now() - navigationStart;

const markersBefore = await page.locator('button[title*="LED"]').count();
const syncLatencies = [];

for (let i = 0; i < 20; i += 1) {
	const status = i % 2 === 0;
	const before = performance.now();
	await db.collection('telemetry_points').insertOne(telemetryDoc(i, status));
	await page.waitForFunction(
		({ expected }) => {
			const titles = [...document.querySelectorAll('button[title*="LED"]')].map((node) => node.getAttribute('title') || '');
			return titles.some((title) => title.includes(expected ? 'ON' : 'OFF'));
		},
		{ expected: status },
		{ timeout: 5000 },
	);
	syncLatencies.push(performance.now() - before);
	await page.waitForTimeout(250);
}

const browserMetrics = await page.evaluate(() => {
	const getEntriesByType = window.__heraRealGetEntriesByType || performance.getEntriesByType.bind(performance);
	const nav = getEntriesByType('navigation')[0];
	const paint = getEntriesByType('paint').map((entry) => ({
		name: entry.name,
		startTime: entry.startTime,
	}));
	return {
		navigation: nav ? {
			domContentLoadedEventEnd: nav.domContentLoadedEventEnd,
			loadEventEnd: nav.loadEventEnd,
			duration: nav.duration,
		} : null,
		paint,
		memory: performance.memory ? {
			usedJSHeapSize: performance.memory.usedJSHeapSize,
			totalJSHeapSize: performance.memory.totalJSHeapSize,
			jsHeapSizeLimit: performance.memory.jsHeapSizeLimit,
		} : null,
	};
});

await browser.close();
await mongo.close();

let lighthouse = null;
if (runLighthouse) {
	const lighthousePath = path.join(outDir, 'lighthouse_floorplan.json');
	await execFileAsync('npx', [
		'lighthouse',
		url,
		'--quiet',
		'--chrome-flags=--headless',
		'--only-categories=performance',
		'--output=json',
		`--output-path=${lighthousePath}`,
	]);
	const raw = JSON.parse(await fs.readFile(lighthousePath, 'utf8'));
	lighthouse = {
		performanceScore: raw.categories.performance.score,
		firstContentfulPaint: raw.audits['first-contentful-paint']?.numericValue,
		largestContentfulPaint: raw.audits['largest-contentful-paint']?.numericValue,
		totalBlockingTime: raw.audits['total-blocking-time']?.numericValue,
		cumulativeLayoutShift: raw.audits['cumulative-layout-shift']?.numericValue,
	};
}

const summary = {
	url,
	initialRenderMs: Number(initialRenderMs.toFixed(3)),
	markersBefore,
	sseToUiLatencyMs: {
		median: Number(percentile(syncLatencies, 50).toFixed(3)),
		p95: Number(percentile(syncLatencies, 95).toFixed(3)),
		min: Number(Math.min(...syncLatencies).toFixed(3)),
		max: Number(Math.max(...syncLatencies).toFixed(3)),
		samples: syncLatencies.length,
	},
	browserMetrics,
	lighthouse,
};

await fs.writeFile(path.join(outDir, 'web_floorplan_perf.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
