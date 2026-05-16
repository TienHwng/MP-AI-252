"""Collect ESP32 heap stability data from serial logs.

Recommended firmware log line every 5s:
    Serial.printf("[HEAP] free=%u min_free=%u largest=%u uptime_ms=%lu\\n",
        ESP.getFreeHeap(), ESP.getMinFreeHeap(), heap_caps_get_largest_free_block(MALLOC_CAP_8BIT), millis());

Example:
    python docs/evaluation/firmware_heap_serial_logger.py --port COM5 --duration-sec 1800
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path

try:
	import serial
	from serial.tools import list_ports
except ImportError:
	serial = None
	list_ports = None

HEAP_RE = re.compile(
	r"\[HEAP\].*?free=(?P<free>\d+).*?min_free=(?P<min_free>\d+).*?largest=(?P<largest>\d+).*?uptime_ms=(?P<uptime_ms>\d+)"
)


def open_serial_port(port: str, baud: int):
	if serial is None:
		raise SystemExit(
			"Missing pyserial. Install it with:\n"
			"  python -m pip install pyserial"
		)

	serial_class = getattr(serial, "Serial", None)
	if serial_class is None:
		module_path = getattr(serial, "__file__", "<unknown>")
		raise SystemExit(
			"Python imported a module named 'serial', but it is not pyserial.\n"
			f"Imported module path: {module_path}\n"
			"Fix the environment with:\n"
			"  python -m pip uninstall -y serial\n"
			"  python -m pip install pyserial"
		)

	try:
		return serial_class(port, baud, timeout=1)
	except Exception as exc:
		available = list_available_ports()
		available_text = "\n".join(f"  {item}" for item in available) or "  <none detected>"
		raise SystemExit(
			f"Could not open serial port {port!r}: {exc}\n"
			"Available serial ports:\n"
			f"{available_text}\n"
			"Check Device Manager or run:\n"
			"  python docs/evaluation/firmware_heap_serial_logger.py --list-ports\n"
			"Then rerun with the detected port, for example --port COM3."
		) from exc


def list_available_ports() -> list[str]:
	if list_ports is None:
		return []
	return [
		f"{port.device} - {port.description}"
		for port in list_ports.comports()
	]


def print_available_ports() -> int:
	ports = list_available_ports()
	if not ports:
		print("No serial ports detected.")
		return 1
	for item in ports:
		print(item)
	return 0


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("--port", help="Windows example: COM5")
	parser.add_argument("--baud", type=int, default=115200)
	parser.add_argument("--duration-sec", type=int, default=1800)
	parser.add_argument("--out-dir", default="docs/evaluation/results")
	parser.add_argument("--list-ports", action="store_true")
	args = parser.parse_args()

	if args.list_ports:
		return print_available_ports()

	if not args.port:
		raise SystemExit("Missing --port. Run with --list-ports to find the ESP32 port.")

	out_dir = Path(args.out_dir)
	out_dir.mkdir(parents=True, exist_ok=True)
	csv_path = out_dir / "firmware_heap_serial.csv"
	summary_path = out_dir / "firmware_heap_serial_summary.json"

	rows = []
	start = time.time()
	with open_serial_port(args.port, args.baud) as ser:
		while time.time() - start < args.duration_sec:
			line = ser.readline().decode("utf-8", errors="replace").strip()
			match = HEAP_RE.search(line)
			if not match:
				continue
			row = {
				"host_timestamp_ms": int(time.time() * 1000),
				"uptime_ms": int(match.group("uptime_ms")),
				"free_heap_bytes": int(match.group("free")),
				"min_free_heap_bytes": int(match.group("min_free")),
				"largest_free_block_bytes": int(match.group("largest")),
			}
			rows.append(row)
			print(row)

	with csv_path.open("w", newline="", encoding="utf-8") as fh:
		writer = csv.DictWriter(
			fh,
			fieldnames=[
				"host_timestamp_ms",
				"uptime_ms",
				"free_heap_bytes",
				"min_free_heap_bytes",
				"largest_free_block_bytes",
			],
		)
		writer.writeheader()
		writer.writerows(rows)

	if rows:
		first = rows[0]
		last = rows[-1]
		free_values = [row["free_heap_bytes"] for row in rows]
		largest_values = [row["largest_free_block_bytes"] for row in rows]
		summary = {
			"samples": len(rows),
			"duration_sec": round((last["host_timestamp_ms"] - first["host_timestamp_ms"]) / 1000, 3),
			"free_heap_start_bytes": first["free_heap_bytes"],
			"free_heap_end_bytes": last["free_heap_bytes"],
			"free_heap_drift_bytes": last["free_heap_bytes"] - first["free_heap_bytes"],
			"free_heap_min_bytes": min(free_values),
			"largest_free_block_min_bytes": min(largest_values),
			"min_free_heap_reported_min_bytes": min(row["min_free_heap_bytes"] for row in rows),
		}
	else:
		summary = {"samples": 0, "error": "No [HEAP] lines captured"}

	summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
	print(json.dumps(summary, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
