"""Nested telemetry schema helpers.

Canonical runtime payload follows backend/MQTT_Broker/mqtt_simulator.py:
sensor values live under sensors.dht20 / sensors.light / sensors.gas and
device states live under devices.<device>.status.
"""

from __future__ import annotations

from typing import Any


DEVICE_KEY_BY_TARGET = {
	"main_led": "led",
	"neo_led": "neo_led",
	"ws2812": "ws2812",
	"relay": "relay",
	"mini_fan": "mini_fan",
}

FLAT_DEVICE_STATUS_KEYS = {
	"led": "led_status",
	"neo_led": "neo_led_status",
	"ws2812": "ws2812_status",
	"relay": "relay_status",
	"mini_fan": "mini_fan_status",
}


def _mapping(value: Any) -> dict:
	return value if isinstance(value, dict) else {}


def _scalar(value: Any) -> Any:
	if isinstance(value, dict):
		return value.get("value")
	return value


def sensor_value(source: dict | None, sensor: str) -> Any:
	"""Read a sensor value from canonical nested telemetry."""
	if not isinstance(source, dict):
		return None
	sensors = _mapping(source.get("sensors")) or source
	sensor = str(sensor or "").strip().lower()

	if sensor in {"temperature", "humidity"}:
		dht20 = _mapping(sensors.get("dht20")) or _mapping(sensors.get("dht"))
		return dht20.get(sensor, sensors.get(sensor))

	if sensor == "light":
		return _scalar(sensors.get("light"))

	if sensor in {"gas", "gas_ppm"}:
		return _scalar(sensors.get("gas", sensors.get("gas_ppm")))

	if sensor == "gas_detected":
		gas = _mapping(sensors.get("gas"))
		return gas.get("detected", sensors.get("gas_detected"))

	if sensor == "anomaly":
		return sensors.get("anomaly", sensors.get("anomaly_score"))

	return _scalar(sensors.get(sensor))


def device_status(source: dict | None, target_or_key: str) -> bool | None:
	"""Read devices.<device>.status from canonical nested telemetry."""
	if not isinstance(source, dict):
		return None
	devices = _mapping(source.get("devices")) or source
	device_key = DEVICE_KEY_BY_TARGET.get(target_or_key, target_or_key)
	device = devices.get(device_key)
	if isinstance(device, dict):
		value = device.get("status")
	elif isinstance(device, bool):
		value = device
	else:
		value = devices.get(FLAT_DEVICE_STATUS_KEYS.get(device_key, ""))

	return value if isinstance(value, bool) else None
