"""Deterministic device side effects for HERA physical control."""

from __future__ import annotations

import threading
from typing import Any

from core.mqtt_service import MQTTService

from domain.devices.device_catalog import (
	DEVICE_STATUS_KEYS,
	DEVICE_TARGETS,
	DEVICE_VALUE_SPECS,
	FAN_START_SPEED,
	SENSOR_VALUE_SPECS,
	coerce_device_value,
	coerce_sensor_value,
	normalize_color_value,
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
			device_name: self._device_status(devices, device_key)
			for device_name, device_key in DEVICE_STATUS_KEYS.items()
		}

	def get_value_readback_report(self) -> dict:
		"""Return nested readback data for adjustable device/sensor values."""
		devices = self.mqtt.get_device_snapshot()
		get_sensor_readings = getattr(self.mqtt, "get_sensor_readings_snapshot", None)
		if callable(get_sensor_readings):
			sensors = get_sensor_readings()
		else:
			snapshot = getattr(self.mqtt, "get_sensor_snapshot", lambda: {})()
			sensors = snapshot.get("sensors", {}) if isinstance(snapshot, dict) else {}
		return {
			"devices": {
				device_name: self._device_payload(devices, device_key)
				for device_name, device_key in DEVICE_STATUS_KEYS.items()
			},
			"sensors": sensors if isinstance(sensors, dict) else {},
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

	def control_device_value(
		self,
		raw_target: Any,
		raw_property: Any,
		raw_value: Any,
	) -> dict:
		coerced = coerce_device_value(raw_target, raw_property, raw_value)
		if not coerced.get("ok"):
			return {
				"ok": False,
				"reason": coerced.get("reason", "invalid_device_value"),
				"target": coerced.get("target") or raw_target,
				"property": coerced.get("property") or raw_property,
				"requested_value": raw_value,
				"valid_targets": sorted(DEVICE_VALUE_SPECS),
				"valid_properties": {
					target: sorted(properties)
					for target, properties in DEVICE_VALUE_SPECS.items()
				},
				"commands_sent": [],
			}

		target = str(coerced["target"])
		with self._get_lock(target):
			return self._control_normalized_value(coerced)

	def set_sensor_value(self, raw_sensor: Any, raw_value: Any) -> dict:
		coerced = coerce_sensor_value(raw_sensor, raw_value)
		if not coerced.get("ok"):
			return {
				"ok": False,
				"reason": coerced.get("reason", "invalid_sensor_value"),
				"sensor": coerced.get("sensor") or raw_sensor,
				"requested_value": raw_value,
				"valid_sensors": sorted(SENSOR_VALUE_SPECS),
				"commands_sent": [],
			}

		sensor = str(coerced["sensor"])
		value = coerced["value"]
		current_value = self._sensor_value(sensor)
		before_state = {sensor: current_value}
		if self._same_value(current_value, value):
			return {
				"ok": True,
				"reason": "already_in_requested_value",
				"sensor": sensor,
				"requested_value": value,
				"states_before": before_state,
				"states_after": self.get_value_readback_report(),
				"changed": [],
				"unchanged": [str(coerced["label"])],
				"commands_sent": [],
			}

		params = {"sensor": sensor, "value": value}
		self.mqtt.publish_rpc("setSensorValue", params)
		return {
			"ok": True,
			"reason": "value_changed",
			"sensor": sensor,
			"requested_value": value,
			"states_before": before_state,
			"states_after": self.get_value_readback_report(),
			"changed": [str(coerced["label"])],
			"unchanged": [],
			"commands_sent": [
				{
					"method": "setSensorValue",
					"params": params,
					"entity_type": "sensor_value",
					"sensor": sensor,
					"expected_value": value,
					"label": str(coerced["label"]),
				}
			],
		}

	def _control_normalized_target(self, target: str, state: bool) -> dict:
		devices = self.mqtt.sensor_state.setdefault("devices", {})
		commands_sent: list[dict] = []
		changed: list[str] = []
		unchanged: list[str] = []
		states_before: dict[str, bool | None] = {}

		for method, device_key, label in DEVICE_TARGETS[target]:
			current_state = self._device_status(devices, device_key)
			states_before[device_key] = current_state
			if self._state_already_satisfied(devices, device_key, state):
				unchanged.append(label)
				continue
			rpc_method, rpc_params = self._state_rpc_payload(method, device_key, state)
			self.mqtt.publish_rpc(rpc_method, rpc_params)
			changed.append(label)
			commands_sent.append(
				{
					"method": rpc_method,
					"params": rpc_params,
					"expected_state": state,
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

	def _control_normalized_value(self, coerced: dict) -> dict:
		target = str(coerced["target"])
		prop = str(coerced["property"])
		value = coerced["value"]
		device_key = str(coerced["device_key"])
		field = str(coerced["field"])
		label = str(coerced["label"])
		method = str(coerced["method"])

		devices = self.mqtt.get_device_snapshot()
		current_value = self._device_field_value(devices, target, field)
		before_state = {device_key: {field: current_value}}
		if self._same_value(current_value, value):
			return {
				"ok": True,
				"reason": "already_in_requested_value",
				"target": target,
				"property": prop,
				"requested_value": value,
				"states_before": before_state,
				"states_after": self.get_value_readback_report(),
				"changed": [],
				"unchanged": [label],
				"commands_sent": [],
			}

		self.mqtt.publish_rpc(method, value)
		return {
			"ok": True,
			"reason": "value_changed",
			"target": target,
			"property": prop,
			"requested_value": value,
			"states_before": before_state,
			"states_after": self.get_value_readback_report(),
			"changed": [label],
			"unchanged": [],
			"commands_sent": [
				{
					"method": method,
					"params": value,
					"entity_type": "device_value",
					"device_key": device_key,
					"target": target,
					"property": prop,
					"field": field,
					"expected_value": value,
					"label": label,
				}
			],
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
			"sensors": self.get_value_readback_report().get("sensors", {}),
			"network": network,
		}

	def _get_lock(self, target: str) -> threading.Lock:
		with self._locks_guard:
			if target not in self._locks:
				self._locks[target] = threading.Lock()
			return self._locks[target]

	@staticmethod
	def _device_status(devices: dict, device_key: str) -> bool | None:
		device = devices.get(device_key)
		if isinstance(device, dict):
			return device.get("status")
		if isinstance(device, bool):
			return device
		flat_key = f"{device_key}_status"
		if device_key == "led":
			flat_key = "led_status"
		if flat_key in devices and isinstance(devices.get(flat_key), bool):
			return devices.get(flat_key)
		return None

	@classmethod
	def _device_payload(cls, devices: dict, device_key: str) -> dict:
		device = devices.get(device_key)
		payload = dict(device) if isinstance(device, dict) else {}
		status = cls._device_status(devices, device_key)
		if status is not None:
			payload.setdefault("status", status)
		flat_fields = {
			"neo_led": {"brightness": "strip_brightness"},
			"ws2812": {
				"brightness": "ws2812_brightness",
				"color": "ws2812_color",
			},
			"mini_fan": {"speed": "fan_speed"},
		}
		for field, flat_key in flat_fields.get(device_key, {}).items():
			if field not in payload and flat_key in devices:
				payload[field] = devices.get(flat_key)
		return payload

	@classmethod
	def _device_field_value(cls, devices: dict, target: str, field: str) -> Any:
		device_key = DEVICE_STATUS_KEYS.get(target)
		if device_key is None:
			return None
		return cls._device_payload(devices, device_key).get(field)

	@classmethod
	def _state_already_satisfied(
		cls,
		devices: dict,
		device_key: str,
		state: bool,
	) -> bool:
		current_state = cls._device_status(devices, device_key)
		if current_state is not state:
			return False
		if device_key == "mini_fan" and state:
			speed = cls._device_payload(devices, device_key).get("speed")
			return isinstance(speed, int | float) and speed >= FAN_START_SPEED
		return True

	@staticmethod
	def _state_rpc_payload(method: str, device_key: str, state: bool) -> tuple[str, Any]:
		if device_key == "mini_fan":
			return "setFanSpeed", FAN_START_SPEED if state else 0
		return method, state

	def _sensor_value(self, sensor: str) -> Any:
		get_sensor_readings = getattr(self.mqtt, "get_sensor_readings_snapshot", None)
		if callable(get_sensor_readings):
			sensors = get_sensor_readings()
		else:
			snapshot = getattr(self.mqtt, "get_sensor_snapshot", lambda: {})()
			sensors = snapshot.get("sensors", {}) if isinstance(snapshot, dict) else {}
		if not isinstance(sensors, dict):
			return None
		if sensor in {"temperature", "humidity"}:
			dht20 = sensors.get("dht20")
			if isinstance(dht20, dict) and sensor in dht20:
				return dht20.get(sensor)
			return sensors.get(sensor)
		if sensor == "light":
			light = sensors.get("light")
			return light.get("value") if isinstance(light, dict) else light
		if sensor == "gas":
			gas = sensors.get("gas")
			return gas.get("value") if isinstance(gas, dict) else gas
		if sensor == "gas_detected":
			gas = sensors.get("gas")
			if isinstance(gas, dict) and "detected" in gas:
				return gas.get("detected")
			return sensors.get("gas_detected")
		return sensors.get(sensor)

	@staticmethod
	def _same_value(left: Any, right: Any) -> bool:
		left_color = normalize_color_value(left)
		right_color = normalize_color_value(right)
		if left_color is not None or right_color is not None:
			return left_color == right_color
		return left == right
