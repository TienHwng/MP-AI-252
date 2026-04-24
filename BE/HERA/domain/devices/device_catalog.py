"""Canonical device target catalog and normalization helpers."""

from __future__ import annotations

from typing import Any

DEVICE_TARGETS = {
	"main_led": [
		("setValueLedBlinky", "led_status", "Main LED"),
	],
	"neo_led": [
		("setValueNeoLed", "neo_led_status", "NeoPixel LED"),
	],
	"ws2812": [
		("setValueWS2812", "ws2812_status", "WS2812 LED"),
	],
	"relay": [
		("setValueRelay", "relay_status", "Relay"),
	],
	"mini_fan": [
		("setValueMiniFan", "mini_fan_status", "Mini fan"),
	],
	"all_lights": [
		("setValueLedBlinky", "led_status", "Main LED"),
		("setValueNeoLed", "neo_led_status", "NeoPixel LED"),
		("setValueWS2812", "ws2812_status", "WS2812 LED"),
	],
	"all_devices": [
		("setValueLedBlinky", "led_status", "Main LED"),
		("setValueNeoLed", "neo_led_status", "NeoPixel LED"),
		("setValueWS2812", "ws2812_status", "WS2812 LED"),
		("setValueRelay", "relay_status", "Relay"),
		("setValueMiniFan", "mini_fan_status", "Mini fan"),
	],
}

DEVICE_STATUS_KEYS = {
	"main_led": "led_status",
	"neo_led": "neo_led_status",
	"ws2812": "ws2812_status",
	"relay": "relay_status",
	"mini_fan": "mini_fan_status",
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
