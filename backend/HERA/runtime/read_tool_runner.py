"""Small read-only tool boundary for live HERA state."""

from __future__ import annotations

from typing import Any

from domain.devices.device_executor import DeviceExecutor


class ReadToolRunner:
	"""Executes read-only runtime tools without policy or side effects."""

	def __init__(
		self,
		mqtt,
		device_executor: DeviceExecutor,
		telemetry_store=None,
	) -> None:
		self.mqtt = mqtt
		self.device_executor = device_executor
		self.telemetry_store = telemetry_store

	def run(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
		args = args or {}
		if name == "get_current_telemetry":
			return {
				"ok": True,
				"name": name,
				"result": self.mqtt.get_sensor_snapshot(),
			}
		if name == "get_device_status":
			return {
				"ok": True,
				"name": name,
				"result": self.device_executor.get_status_result(
					args.get("device_target")
				),
			}
		if name == "get_telemetry_window":
			if self.telemetry_store is None:
				return {
					"ok": False,
					"name": name,
					"reason": "telemetry_store_not_configured",
					"result": {},
				}
			window_seconds = int(args.get("window_seconds") or 0)
			if window_seconds <= 0:
				return {
					"ok": False,
					"name": name,
					"reason": "invalid_window_seconds",
					"result": {},
				}
			return {
				"ok": True,
				"name": name,
				"result": self.telemetry_store.recent_summary_seconds(
					user_id=args.get("user_id"),
					window_seconds=window_seconds,
					limit=int(args.get("limit") or max(20, min(300, window_seconds * 4))),
				),
			}
		return {
			"ok": False,
			"name": name,
			"reason": "unknown_read_tool",
			"result": {},
		}
