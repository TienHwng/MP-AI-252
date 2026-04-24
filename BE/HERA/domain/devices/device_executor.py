"""Deterministic device side effects for HERA physical control."""

from __future__ import annotations

import threading
from typing import Any

from core.mqtt_service import MQTTService

from domain.devices.device_catalog import (
	DEVICE_STATUS_KEYS,
	DEVICE_TARGETS,
	normalize_device_target,
)


class DeviceExecutor:
	"""Owns device read/write operations against the current MQTT service."""

	def __init__(self, mqtt: MQTTService) -> None:
		self.mqtt = mqtt
		self._locks: dict[str, threading.Lock] = {}
		self._locks_guard = threading.Lock()

	def get_device_status_report(self) -> dict:
		devices = self.mqtt.get_device_snapshot()
		return {
			device_name: devices.get(status_key)
			for device_name, status_key in DEVICE_STATUS_KEYS.items()
		}

	def control_device_state(self, raw_target: Any, state: bool) -> dict:
		target = normalize_device_target(raw_target)
		if target is None:
			return {
				"ok": False,
				"reason": "invalid_target",
				"target": raw_target,
				"valid_targets": list(DEVICE_TARGETS),
				"requested_state": state,
				"commands_sent": [],
			}

		with self._get_lock(target):
			return self._control_normalized_target(target, state)

	def _control_normalized_target(self, target: str, state: bool) -> dict:
		devices = self.mqtt.sensor_state.setdefault("devices", {})
		commands_sent: list[dict] = []
		changed: list[str] = []
		unchanged: list[str] = []
		states_before: dict[str, bool | None] = {}

		for method, device_key, label in DEVICE_TARGETS[target]:
			current_state = devices.get(device_key)
			states_before[device_key] = current_state
			if current_state is state:
				unchanged.append(label)
				continue
			self.mqtt.publish_rpc(method, state)
			changed.append(label)
			commands_sent.append(
				{
					"method": method,
					"params": state,
					"device_key": device_key,
					"label": label,
				}
			)

		if changed and unchanged:
			reason = "partially_changed"
		elif changed:
			reason = "state_changed"
		else:
			reason = "already_in_requested_state"

		return {
			"ok": True,
			"reason": reason,
			"target": target,
			"requested_state": state,
			"states_before": states_before,
			"states_after": self.get_device_status_report(),
			"changed": changed,
			"unchanged": unchanged,
			"commands_sent": commands_sent,
		}

	def get_status_result(self, raw_target: Any | None = None) -> dict:
		target = normalize_device_target(raw_target) if raw_target is not None else None
		return {
			"ok": True,
			"reason": "status_requested",
			"target": target,
			"device_status": self.get_device_status_report(),
			"commands_sent": [],
		}

	def get_runtime_state(self) -> dict:
		get_network_snapshot = getattr(self.mqtt, "get_network_snapshot", None)
		network = get_network_snapshot() if callable(get_network_snapshot) else {}
		return {
			"devices": self.mqtt.get_device_snapshot(),
			"network": network,
		}

	def _get_lock(self, target: str) -> threading.Lock:
		with self._locks_guard:
			if target not in self._locks:
				self._locks[target] = threading.Lock()
			return self._locks[target]
