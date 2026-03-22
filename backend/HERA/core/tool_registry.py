"""
Tool Registry
==============
Defines available tools (LED control, sensor query, …) and executes them.
Agents reference tools by name; the registry maps names to actual side-effects.
"""

from __future__ import annotations

import json
from typing import Any

from core.mqtt_service import MQTTService


# ── helpers ───────────────────────────────────────────────────

def make_tool_def(name: str, desc: str, parameters: dict | None = None) -> dict:
    """Build an OpenAI-style function tool definition."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": parameters or {
                "type": "object", "properties": {}, "required": [],
            },
        },
    }


# ── registry class ────────────────────────────────────────────

class ToolRegistry:
    """
    Holds tool *definitions* (JSON schemas for the LLM) **and**
    tool *executors* (functions that carry out the action).
    """

    def __init__(self, mqtt: MQTTService) -> None:
        self._mqtt = mqtt
        self._executors: dict[str, Any] = {}
        self.definitions: list[dict] = []
        self._register_builtins()

    # ── public API ────────────────────────────────────────────

    def execute(self, name: str, args: dict) -> str:
        fn = self._executors.get(name)
        if fn is None:
            return f"Unknown tool: {name}"
        return fn(args)

    def get_definitions(self, names: list[str] | None = None) -> list[dict]:
        """Return tool schemas — optionally filtered by name list."""
        if names is None:
            return list(self.definitions)
        name_set = set(names)
        return [d for d in self.definitions if d["function"]["name"] in name_set]

    # ── registration ──────────────────────────────────────────

    def _register(self, name: str, desc: str, executor, params=None):
        self.definitions.append(make_tool_def(name, desc, params))
        self._executors[name] = executor

    def _register_builtins(self):
        mqtt = self._mqtt

        # single-LED helpers
        _singles = {
            "turn_on_led": (
                "Turn ON the white indicator LED (main LED). "
                "Use for 'main LED', 'white LED', 'indicator LED'.",
                "setValueLedBlinky", True, "led_state", True,
                "LED has been turned ON.",
            ),
            "turn_off_led": (
                "Turn OFF the white indicator LED (main LED). "
                "Use for 'main LED', 'white LED', 'indicator LED'.",
                "setValueLedBlinky", False, "led_state", False,
                "LED has been turned OFF.",
            ),
            "turn_on_neo_led": (
                "Turn ON the NeoPixel RGB LED (colorful LED). "
                "Use for 'NeoPixel', 'RGB LED', 'colorful LED', 'color LED'.",
                "setValueNeoLed", True, "neo_led_state", True,
                "NeoPixel LED has been turned ON.",
            ),
            "turn_off_neo_led": (
                "Turn OFF the NeoPixel RGB LED (colorful LED). "
                "Use for 'NeoPixel', 'RGB LED', 'colorful LED', 'color LED'.",
                "setValueNeoLed", False, "neo_led_state", False,
                "NeoPixel LED has been turned OFF.",
            ),
        }

        for tool_name, (desc, method, param, skey, sval, msg) in _singles.items():
            def _make(m=method, p=param, sk=skey, sv=sval, mg=msg):
                def _exec(_args):
                    mqtt.publish_rpc(m, p)
                    mqtt.sensor_state[sk] = sv
                    return mg
                return _exec
            self._register(tool_name, desc, _make())

        # all-lights
        def _on_all(_a):
            mqtt.publish_rpc("setValueLedBlinky", True)
            mqtt.publish_rpc("setValueNeoLed", True)
            mqtt.sensor_state["led_state"] = True
            mqtt.sensor_state["neo_led_state"] = True
            return "Both LEDs have been turned ON."

        def _off_all(_a):
            mqtt.publish_rpc("setValueLedBlinky", False)
            mqtt.publish_rpc("setValueNeoLed", False)
            mqtt.sensor_state["led_state"] = False
            mqtt.sensor_state["neo_led_state"] = False
            return "Both LEDs have been turned OFF."

        self._register(
            "turn_on_all_lights",
            "Turn ON both LEDs (white + NeoPixel). "
            "Use for 'all lights', 'both lights', 'all LEDs'.",
            _on_all,
        )
        self._register(
            "turn_off_all_lights",
            "Turn OFF both LEDs (white + NeoPixel). "
            "Use for 'all lights off', 'both off', 'turn off everything'.",
            _off_all,
        )

        # sensor query
        def _get_status(_a):
            return json.dumps(mqtt.get_sensor_snapshot(), indent=2)

        self._register(
            "get_sensor_status",
            "Get current sensor readings: temperature, humidity, "
            "anomaly score, and LED states.",
            _get_status,
        )
