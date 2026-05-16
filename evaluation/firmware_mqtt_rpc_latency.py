"""Measure ESP32 MQTT RPC round-trip latency.

The ESP32 subscribes to:
    v1/devices/me/rpc/request/+
and publishes responses to:
    v1/devices/me/rpc/response/<request_id>

Example:
    python docs/evaluation/firmware_mqtt_rpc_latency.py --broker 10.0.2.131 --count 100
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt


def percentile(values: list[float], pct: float) -> float | None:
	if not values:
		return None
	ordered = sorted(values)
	index = min(len(ordered) - 1, max(0, round((pct / 100) * (len(ordered) - 1))))
	return ordered[index]


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("--broker", default="127.0.0.1")
	parser.add_argument("--port", type=int, default=1883)
	parser.add_argument("--count", type=int, default=100)
	parser.add_argument("--interval-ms", type=int, default=250)
	parser.add_argument("--timeout-ms", type=int, default=3000)
	parser.add_argument("--method", default="setValueLedBlinky")
	parser.add_argument("--params", default="true", help="JSON value, e.g. true, false, 128")
	parser.add_argument("--request-prefix", default="v1/devices/me/rpc/request")
	parser.add_argument("--response-prefix", default="v1/devices/me/rpc/response")
	parser.add_argument("--out-dir", default="docs/evaluation/results")
	args = parser.parse_args()

	try:
		params = json.loads(args.params)
	except json.JSONDecodeError as exc:
		raise SystemExit(f"--params must be valid JSON: {exc}") from exc

	out_dir = Path(args.out_dir)
	out_dir.mkdir(parents=True, exist_ok=True)
	csv_path = out_dir / "firmware_rpc_latency.csv"
	summary_path = out_dir / "firmware_rpc_latency_summary.json"

	pending: dict[str, dict] = {}
	rows: list[dict] = []
	lock = threading.Lock()
	connected = threading.Event()

	def on_connect(client, _userdata, _flags, rc):
		if rc != 0:
			raise RuntimeError(f"MQTT connect failed with rc={rc}")
		client.subscribe(f"{args.response_prefix}/+")
		connected.set()

	def on_message(_client, _userdata, msg):
		request_id = msg.topic.rsplit("/", 1)[-1]
		now = time.perf_counter_ns()
		with lock:
			item = pending.pop(request_id, None)
		if item is None:
			return
		latency_ms = (now - item["sent_ns"]) / 1_000_000
		try:
			response = json.loads(msg.payload.decode("utf-8"))
		except Exception:
			response = {"raw": msg.payload.decode("utf-8", errors="replace")}
		rows.append(
			{
				"request_id": request_id,
				"method": item["method"],
				"params": json.dumps(item["params"]),
				"latency_ms": round(latency_ms, 3),
				"ok": "error" not in response,
				"response": json.dumps(response, ensure_ascii=False),
			}
		)

	client = mqtt.Client(client_id=f"hera-rpc-latency-{int(time.time())}")
	client.on_connect = on_connect
	client.on_message = on_message
	client.connect(args.broker, args.port, keepalive=30)
	client.loop_start()
	if not connected.wait(5):
		raise SystemExit("Timed out waiting for MQTT connection")

	for index in range(args.count):
		request_id = f"eval-{int(time.time() * 1000)}-{index}"
		payload = {"method": args.method, "params": params}
		with lock:
			pending[request_id] = {
				"sent_ns": time.perf_counter_ns(),
				"method": args.method,
				"params": params,
			}
		client.publish(f"{args.request_prefix}/{request_id}", json.dumps(payload))
		time.sleep(args.interval_ms / 1000)

	deadline = time.time() + (args.timeout_ms / 1000)
	while time.time() < deadline:
		with lock:
			if not pending:
				break
		time.sleep(0.05)

	with lock:
		for request_id, item in pending.items():
			rows.append(
				{
					"request_id": request_id,
					"method": item["method"],
					"params": json.dumps(item["params"]),
					"latency_ms": "",
					"ok": False,
					"response": "timeout",
				}
			)

	client.loop_stop()
	client.disconnect()

	with csv_path.open("w", newline="", encoding="utf-8") as fh:
		writer = csv.DictWriter(
			fh,
			fieldnames=["request_id", "method", "params", "latency_ms", "ok", "response"],
		)
		writer.writeheader()
		writer.writerows(rows)

	latencies = [float(row["latency_ms"]) for row in rows if row["latency_ms"] != ""]
	ok_count = sum(1 for row in rows if row["ok"] is True)
	summary = {
		"total": len(rows),
		"successful": ok_count,
		"success_rate_percent": round(ok_count / len(rows) * 100, 2) if rows else 0,
		"timeout_count": sum(1 for row in rows if row["response"] == "timeout"),
		"latency_ms": {
			"mean": round(statistics.mean(latencies), 3) if latencies else None,
			"median": round(statistics.median(latencies), 3) if latencies else None,
			"p95": round(percentile(latencies, 95), 3) if latencies else None,
			"min": round(min(latencies), 3) if latencies else None,
			"max": round(max(latencies), 3) if latencies else None,
		},
	}
	summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
	print(json.dumps(summary, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

