"""
Tool Registry
=============
Defines available tools (LED control, sensor query, ...) and executes them.
Agents reference tools by name; the registry maps names to actual side-effects.
"""

from __future__ import annotations

import json
from typing import Any

from core.mqtt_service import MQTTService


def make_tool_def(name: str, desc: str, parameters: dict | None = None) -> dict:
    """Build an OpenAI-style function tool definition."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": parameters or {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }


_LIGHT_TARGETS = {
    "main_led": [
        ("setValueLedBlinky", "led_status"),
    ],
    "neo_led": [
        ("setValueNeoLed", "neo_led_status"),
    ],
    "all_lights": [
        ("setValueLedBlinky", "led_status"),
        ("setValueNeoLed", "neo_led_status"),
    ],
}

_LIGHT_ALIASES = {
    "main": "main_led",
    "main_led": "main_led",
    "main led": "main_led",
    "indicator": "main_led",
    "indicator_led": "main_led",
    "indicator led": "main_led",
    "white": "main_led",
    "white_led": "main_led",
    "white led": "main_led",
    "led": "main_led",
    "neo": "neo_led",
    "neo_led": "neo_led",
    "neo led": "neo_led",
    "neopixel": "neo_led",
    "rgb": "neo_led",
    "rgb_led": "neo_led",
    "rgb led": "neo_led",
    "color": "neo_led",
    "color_led": "neo_led",
    "color led": "neo_led",
    "all": "all_lights",
    "both": "all_lights",
    "lights": "all_lights",
    "all_lights": "all_lights",
    "all lights": "all_lights",
    "both_lights": "all_lights",
    "both lights": "all_lights",
}

_LIGHT_TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "light_target": {
            "type": "string",
            "enum": ["main_led", "neo_led", "all_lights"],
            "description": (
                "Which light to control: main_led for the white indicator LED, "
                "neo_led for the NeoPixel RGB LED, all_lights for both LEDs."
            ),
        },
    },
    "required": ["light_target"],
}


def _normalize_light_target(raw_target: Any) -> str | None:
    if not isinstance(raw_target, str):
        return None
    key = raw_target.strip().lower().replace("-", "_")
    key = " ".join(key.split())
    return _LIGHT_ALIASES.get(key) or _LIGHT_ALIASES.get(key.replace("_", " "))


class ToolRegistry:
    """
    Holds tool definitions (JSON schemas for the LLM) and tool executors.
    """

    def __init__(self, mqtt: MQTTService) -> None:
        self._mqtt = mqtt
        self._executors: dict[str, Any] = {}
        self.definitions: list[dict] = []
        self._register_builtins()

    def execute(self, name: str, args: dict) -> str:
        fn = self._executors.get(name)
        if fn is None:
            return f"Unknown tool: {name}"
        return fn(args)

    def get_definitions(self, names: list[str] | None = None) -> list[dict]:
        """Return tool schemas, optionally filtered by name list."""
        if names is None:
            return list(self.definitions)
        name_set = set(names)
        return [d for d in self.definitions if d["function"]["name"] in name_set]

    def _register(self, name: str, desc: str, executor, params=None) -> None:
        self.definitions.append(make_tool_def(name, desc, params))
        self._executors[name] = executor

    def _register_builtins(self) -> None:
        mqtt = self._mqtt

        def _set_light_state(args: dict, state: bool) -> str:
            target = _normalize_light_target(args.get("light_target"))
            if target is None:
                valid = ", ".join(_LIGHT_TARGETS)
                return f"Invalid light_target. Use one of: {valid}."

            for method, device_key in _LIGHT_TARGETS[target]:
                mqtt.publish_rpc(method, state)
                devices = mqtt.sensor_state.setdefault("devices", {})
                devices[device_key] = state

            action = "ON" if state else "OFF"
            label = {
                "main_led": "Main LED",
                "neo_led": "NeoPixel LED",
                "all_lights": "All lights",
            }[target]
            return f"{label} turned {action}."

        self._register(
            "turn_on_light",
            "Turn ON one light or both lights. Use light_target="
            "main_led, neo_led, or all_lights.",
            lambda args: _set_light_state(args, True),
            _LIGHT_TOOL_PARAMS,
        )
        self._register(
            "turn_off_light",
            "Turn OFF one light or both lights. Use light_target="
            "main_led, neo_led, or all_lights.",
            lambda args: _set_light_state(args, False),
            _LIGHT_TOOL_PARAMS,
        )

        # Legacy aliases kept as executors for backward compatibility.
        self._executors["turn_on_led"] = (
            lambda _args: _set_light_state({"light_target": "main_led"}, True)
        )
        self._executors["turn_off_led"] = (
            lambda _args: _set_light_state({"light_target": "main_led"}, False)
        )
        self._executors["turn_on_neo_led"] = (
            lambda _args: _set_light_state({"light_target": "neo_led"}, True)
        )
        self._executors["turn_off_neo_led"] = (
            lambda _args: _set_light_state({"light_target": "neo_led"}, False)
        )
        self._executors["turn_on_all_lights"] = (
            lambda _args: _set_light_state({"light_target": "all_lights"}, True)
        )
        self._executors["turn_off_all_lights"] = (
            lambda _args: _set_light_state({"light_target": "all_lights"}, False)
        )

        def _get_status(_args: dict) -> str:
            return json.dumps(mqtt.get_sensor_snapshot(), indent=2)

        self._register(
            "get_sensor_status",
            "Get current sensor readings: temperature, humidity, "
            "anomaly score, and LED states.",
            _get_status,
        )
