"""Canonical device target/value catalog and normalization helpers."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

DEVICE_TARGETS = {
	"main_led": [
		("setValueLedBlinky", "led", "Main LED"),
	],
	"neo_led": [
		("setValueNeoLed", "neo_led", "NeoPixel LED"),
	],
	"ws2812": [
		("setValueWS2812", "ws2812", "WS2812 LED"),
	],
	"relay": [
		("setValueRelay", "relay", "Relay"),
	],
	"mini_fan": [
		("setValueMiniFan", "mini_fan", "Mini fan"),
	],
	"all_lights": [
		("setValueLedBlinky", "led", "Main LED"),
		("setValueNeoLed", "neo_led", "NeoPixel LED"),
		("setValueWS2812", "ws2812", "WS2812 LED"),
	],
	"all_devices": [
		("setValueLedBlinky", "led", "Main LED"),
		("setValueNeoLed", "neo_led", "NeoPixel LED"),
		("setValueWS2812", "ws2812", "WS2812 LED"),
		("setValueRelay", "relay", "Relay"),
		("setValueMiniFan", "mini_fan", "Mini fan"),
	],
}

DEVICE_STATUS_KEYS = {
	"main_led": "led",
	"neo_led": "neo_led",
	"ws2812": "ws2812",
	"relay": "relay",
	"mini_fan": "mini_fan",
}

# Physical placement catalog for user-facing device references.
# This mirrors the House/FloorPlan placement so chat users can refer to
# devices by room instead of internal target IDs.
DEVICE_PLACEMENTS: dict[str, dict[str, Any]] = {
	"main_led": {
		"label": "Living room light",
		"type": "light",
		"room": "Living Room",
		"aliases": (
			"living room light",
			"living room led",
			"den phong khach",
			"đèn phòng khách",
			"phong khach light",
		),
	},
	"neo_led": {
		"label": "Bedroom light",
		"type": "light",
		"room": "Bedroom",
		"aliases": (
			"bedroom light",
			"bedroom led",
			"den phong ngu",
			"đèn phòng ngủ",
			"phong ngu light",
		),
	},
	"ws2812": {
		"label": "Toilet light",
		"type": "light",
		"room": "Toilet",
		"aliases": (
			"toilet light",
			"bathroom light",
			"restroom light",
			"den nha ve sinh",
			"đèn nhà vệ sinh",
			"den toilet",
			"đèn toilet",
		),
	},
	"mini_fan": {
		"label": "Living room fan",
		"type": "fan",
		"room": "Living Room",
		"aliases": (
			"living room fan",
			"fan living room",
			"quat phong khach",
			"quạt phòng khách",
		),
	},
	"relay": {
		"label": "Living room TV",
		"type": "relay",
		"room": "Living Room",
		"aliases": (
			"living room tv",
			"tv living room",
			"tivi phong khach",
			"tv phòng khách",
			"ti vi phòng khách",
		),
	},
}

LIGHT_PLACEMENTS = {
	target: placement
	for target, placement in DEVICE_PLACEMENTS.items()
	if placement.get("type") == "light"
}

# Scene catalog — mirrors the frontend's handleActivateScene logic exactly.
# Each scene is a list of step dicts:
#   {"type": "state",  "target": <device_target>, "state": <bool>}
#   {"type": "value",  "target": <device_target>, "property": <str>, "value": <any>}
SCENE_CATALOG: dict[str, list[dict]] = {
	"movie": [
		{"type": "state", "target": "main_led",  "state": False},
		{"type": "state", "target": "neo_led",   "state": False},
		{"type": "state", "target": "ws2812",    "state": False},
		{"type": "state", "target": "mini_fan",  "state": True},
		{"type": "state", "target": "relay",     "state": True},
		{"type": "value", "target": "neo_led",   "property": "brightness", "value": 0},
		{"type": "value", "target": "ws2812",    "property": "brightness", "value": 0},
	],
	"sleep": [
		{"type": "state", "target": "main_led",  "state": False},
		{"type": "state", "target": "neo_led",   "state": False},
		{"type": "state", "target": "ws2812",    "state": False},
		{"type": "value", "target": "neo_led",   "property": "brightness", "value": 0},
		{"type": "value", "target": "ws2812",    "property": "brightness", "value": 0},
	],
	"away": [
		{"type": "state", "target": "main_led",  "state": False},
		{"type": "state", "target": "neo_led",   "state": False},
		{"type": "state", "target": "ws2812",    "state": False},
		{"type": "state", "target": "mini_fan",  "state": False},
		{"type": "state", "target": "relay",     "state": False},
		{"type": "value", "target": "neo_led",   "property": "brightness", "value": 0},
		{"type": "value", "target": "ws2812",    "property": "brightness", "value": 0},
		{"type": "value", "target": "mini_fan",  "property": "speed",      "value": 0},
	],
}

SCENE_LABELS: dict[str, str] = {
	"movie": "Movie Mode",
	"sleep": "Sleep Mode",
	"away":  "Away Mode",
}

DEVICE_VALUE_SPECS = {
	"main_led": {
		"brightness": {
			"method": "setLedBrightness",
			"device_key": "led",
			"field": "brightness",
			"label": "Main LED brightness",
			"type": "int",
			"minimum": 0,
			"maximum": 1023,
		},
	},
	"neo_led": {
		"brightness": {
			"method": "setStripBrightness",
			"device_key": "neo_led",
			"field": "brightness",
			"label": "NeoPixel LED brightness",
			"type": "int",
			"minimum": 0,
			"maximum": 255,
		},
	},
	"ws2812": {
		"brightness": {
			"method": "setWS2812Brightness",
			"device_key": "ws2812",
			"field": "brightness",
			"label": "WS2812 LED brightness",
			"type": "int",
			"minimum": 0,
			"maximum": 255,
		},
		"color": {
			"method": "setWS2812Color",
			"device_key": "ws2812",
			"field": "color",
			"label": "WS2812 LED color",
			"type": "color",
		},
	},
	"mini_fan": {
		"speed": {
			"method": "setFanSpeed",
			"device_key": "mini_fan",
			"field": "speed",
			"label": "Mini fan speed",
			"type": "int",
			"minimum": 0,
			"maximum": 1023,
		},
	},
}

DEVICE_VALUE_PROPERTY_ALIASES = {
	"brightness": "brightness",
	"bright": "brightness",
	"intensity": "brightness",
	"level": "brightness",
	"speed": "speed",
	"fan_speed": "speed",
	"color": "color",
	"colour": "color",
	"rgb": "color",
}

SENSOR_VALUE_SPECS = {
	"temperature": {"type": "number", "label": "temperature"},
	"humidity": {"type": "number", "label": "humidity"},
	"light": {"type": "number", "label": "light"},
	"gas": {"type": "number", "label": "gas"},
	"gas_detected": {"type": "bool", "label": "gas detected"},
}

SENSOR_ALIASES = {
	"temperature": "temperature",
	"temp": "temperature",
	"humidity": "humidity",
	"humi": "humidity",
	"light": "light",
	"lux": "light",
	"gas": "gas",
	"gas_ppm": "gas",
	"gas_detected": "gas_detected",
	"gasdetected": "gas_detected",
}

DEVICE_TOOL_PARAMS = {
	"type": "object",
	"properties": {
		"device_target": {
			"type": "string",
			"enum": [
				"main_led",
				"neo_led",
				"ws2812",
				"relay",
				"mini_fan",
				"all_lights",
				"all_devices",
			],
			"description": (
				"Which device to control: main_led, neo_led, ws2812, relay, "
				"mini_fan, all_lights, or all_devices."
			),
		},
	},
	"required": ["device_target"],
}

DEVICE_VALUE_TOOL_PARAMS = {
	"type": "object",
	"properties": {
		"device_target": {
			"type": "string",
			"enum": sorted(DEVICE_VALUE_SPECS),
			"description": (
				"Concrete device whose adjustable value should change: "
				"neo_led, ws2812, or mini_fan."
			),
		},
		"property": {
			"type": "string",
			"enum": ["brightness", "speed", "color"],
			"description": (
				"Value to set. Supported pairs: neo_led brightness, "
				"ws2812 brightness/color, mini_fan speed."
			),
		},
		"value": {
			"oneOf": [
				{"type": "integer"},
				{"type": "number"},
				{"type": "string"},
				{
					"type": "object",
					"properties": {
						"r": {"type": "integer", "minimum": 0, "maximum": 255},
						"g": {"type": "integer", "minimum": 0, "maximum": 255},
						"b": {"type": "integer", "minimum": 0, "maximum": 255},
					},
					"required": ["r", "g", "b"],
				},
			],
			"description": (
				"Brightness is 0..255, fan speed is 0..1023, and color is "
				"#RRGGBB or an object with r/g/b channels."
			),
		},
	},
	"required": ["device_target", "property", "value"],
}

SENSOR_VALUE_TOOL_PARAMS = {
	"type": "object",
	"properties": {
		"sensor": {
			"type": "string",
			"enum": ["temperature", "humidity", "light", "gas", "gas_detected"],
			"description": (
				"Simulator sensor value to override. gas_ppm is accepted as "
				"an alias for gas by the runtime."
			),
		},
		"value": {
			"oneOf": [
				{"type": "integer"},
				{"type": "number"},
				{"type": "boolean"},
			],
			"description": (
				"Numeric value for temperature/humidity/light/gas, or boolean "
				"for gas_detected."
			),
		},
	},
	"required": ["sensor", "value"],
}

LIGHT_TARGETS = {
	key: value
	for key, value in DEVICE_TARGETS.items()
	if key in {"main_led", "neo_led", "all_lights"}
}

LIGHT_TOOL_PARAMS = {
	"type": "object",
	"properties": {
		"light_target": {
			"type": "string",
			"enum": ["main_led", "neo_led", "all_lights"],
			"description": (
				"Which light to control: main_led for the white indicator LED, "
				"neo_led for the NeoPixel RGB LED, all_lights for all LEDs."
			),
		},
	},
	"required": ["light_target"],
}


def normalize_device_target(raw_target: Any) -> str | None:
	if not isinstance(raw_target, str):
		return None
	key = "_".join(raw_target.strip().lower().replace("-", " ").split())
	if key in DEVICE_TARGETS:
		return key
	return None


def normalize_light_target(raw_target: Any) -> str | None:
	target = normalize_device_target(raw_target)
	if target in LIGHT_TARGETS:
		return target
	return None


def placement_prompt_lines() -> str:
	lines = []
	for target, placement in DEVICE_PLACEMENTS.items():
		lines.append(
			f"- {target}: {placement['label']} ({placement['room']}, {placement['type']})"
		)
	return "\n".join(lines)


def user_target_options(kind: str | None = None) -> list[dict[str, str]]:
	options = []
	for target, placement in DEVICE_PLACEMENTS.items():
		if kind is not None and placement.get("type") != kind:
			continue
		options.append(
			{
				"target": target,
				"label": str(placement["label"]),
				"room": str(placement["room"]),
				"type": str(placement["type"]),
			}
		)
	return options


def resolve_placed_device_reference(text: str, *, kind: str | None = None) -> str | None:
	normalized = _fold_text(text)
	if not normalized:
		return None
	matches = []
	for target, placement in DEVICE_PLACEMENTS.items():
		if kind is not None and placement.get("type") != kind:
			continue
		candidates = [
			str(placement.get("label") or ""),
			str(placement.get("room") or ""),
			*(str(alias) for alias in placement.get("aliases", ())),
		]
		for candidate in candidates:
			folded_candidate = _fold_text(candidate)
			if folded_candidate and folded_candidate in normalized:
				matches.append(target)
				break
	return matches[0] if len(set(matches)) == 1 else None


def normalize_device_value_property(raw_property: Any) -> str | None:
	if not isinstance(raw_property, str):
		return None
	key = "_".join(raw_property.strip().lower().replace("-", " ").split())
	return DEVICE_VALUE_PROPERTY_ALIASES.get(key)


def normalize_sensor_target(raw_sensor: Any) -> str | None:
	if not isinstance(raw_sensor, str):
		return None
	key = "_".join(raw_sensor.strip().lower().replace("-", " ").split())
	return SENSOR_ALIASES.get(key)


def get_device_value_spec(raw_target: Any, raw_property: Any) -> dict | None:
	target = normalize_device_target(raw_target)
	prop = normalize_device_value_property(raw_property)
	if target is None or prop is None:
		return None
	spec = DEVICE_VALUE_SPECS.get(target, {}).get(prop)
	if spec is None:
		return None
	return {"target": target, "property": prop, **spec}


def coerce_device_value(raw_target: Any, raw_property: Any, raw_value: Any) -> dict:
	spec = get_device_value_spec(raw_target, raw_property)
	if spec is None:
		return {
			"ok": False,
			"reason": "unsupported_device_value",
			"target": normalize_device_target(raw_target),
			"property": normalize_device_value_property(raw_property),
		}

	if spec["type"] == "int":
		value = _coerce_int(raw_value)
		if value is None:
			return {**spec, "ok": False, "reason": "value_must_be_integer"}
		minimum = int(spec["minimum"])
		maximum = int(spec["maximum"])
		if value < minimum or value > maximum:
			return {
				**spec,
				"ok": False,
				"reason": "value_out_of_range",
				"minimum": minimum,
				"maximum": maximum,
			}
		return {**spec, "ok": True, "value": value}

	color = normalize_color_value(raw_value)
	if color is None:
		return {**spec, "ok": False, "reason": "invalid_color_value"}
	return {**spec, "ok": True, "value": color}


def coerce_sensor_value(raw_sensor: Any, raw_value: Any) -> dict:
	sensor = normalize_sensor_target(raw_sensor)
	if sensor not in SENSOR_VALUE_SPECS:
		return {
			"ok": False,
			"reason": "invalid_sensor",
			"sensor": sensor,
		}
	spec = SENSOR_VALUE_SPECS[sensor]
	if spec["type"] == "bool":
		value = _coerce_bool(raw_value)
		if value is None:
			return {
				"ok": False,
				"reason": "value_must_be_boolean",
				"sensor": sensor,
				**spec,
			}
		return {"ok": True, "sensor": sensor, "value": value, **spec}
	value = _coerce_number(raw_value)
	if value is None:
		return {
			"ok": False,
			"reason": "value_must_be_numeric",
			"sensor": sensor,
			**spec,
		}
	return {"ok": True, "sensor": sensor, "value": value, **spec}


def normalize_color_value(raw_value: Any) -> str | None:
	if isinstance(raw_value, str):
		value = raw_value.strip()
		if value.startswith(("0x", "0X")):
			value = value[2:]
		if value.startswith("#"):
			value = value[1:]
		if re.fullmatch(r"[0-9a-fA-F]{6}", value):
			return f"#{value.upper()}"
		return None
	if isinstance(raw_value, dict):
		channels = []
		for key in ("r", "g", "b"):
			channel = _coerce_int(raw_value.get(key))
			if channel is None or channel < 0 or channel > 255:
				return None
			channels.append(channel)
		return "#{:02X}{:02X}{:02X}".format(*channels)
	return None


def _coerce_int(value: Any) -> int | None:
	if isinstance(value, bool):
		return None
	if isinstance(value, int):
		return value
	if isinstance(value, float) and value.is_integer():
		return int(value)
	if isinstance(value, str):
		try:
			number = float(value.strip().replace(",", "."))
		except ValueError:
			return None
		if number.is_integer():
			return int(number)
	return None


def _coerce_number(value: Any) -> int | float | None:
	if isinstance(value, bool):
		return None
	if isinstance(value, int | float):
		return value
	if isinstance(value, str):
		try:
			return float(value.strip().replace(",", "."))
		except ValueError:
			return None
	return None


def _coerce_bool(value: Any) -> bool | None:
	if isinstance(value, bool):
		return value
	if isinstance(value, int | float):
		if value == 1:
			return True
		if value == 0:
			return False
	if isinstance(value, str):
		normalized = value.strip().lower()
		if normalized in {"1", "true", "yes", "on", "detected"}:
			return True
		if normalized in {"0", "false", "no", "off", "clear"}:
			return False
	return None


def _fold_text(value: str) -> str:
	raw = (value or "").replace("đ", "d").replace("Đ", "D")
	normalized = unicodedata.normalize("NFD", raw)
	without_marks = "".join(
		ch for ch in normalized if unicodedata.category(ch) != "Mn"
	)
	return " ".join(without_marks.lower().split())
