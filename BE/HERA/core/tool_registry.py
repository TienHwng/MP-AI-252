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

DEVICE_ALIASES = {
    "main": "main_led",
    "indicator": "main_led",
    "white": "main_led",
    "led": "main_led",
    "main_light": "main_led",
    "white_led": "main_led",
    "neo": "neo_led",
    "rgb": "neo_led",
    "color": "neo_led",
    "neopixel": "neo_led",
    "neo_pixel": "neo_led",
    "ws": "ws2812",
    "ws2812_led": "ws2812",
    "strip": "ws2812",
    "strip_led": "ws2812",
    "fan": "mini_fan",
    "mini": "mini_fan",
    "mini_fan": "mini_fan",
    "quat": "mini_fan",
    "quạt": "mini_fan",
    "relay": "relay",
    "den": "all_lights",
    "đèn": "all_lights",
    "tat_ca_den": "all_lights",
    "tất_cả_đèn": "all_lights",
    "all": "all_lights",
    "both": "all_lights",
    "lights": "all_lights",
    "all_lights": "all_lights",
    "everything": "all_devices",
    "all_devices": "all_devices",
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
    return DEVICE_ALIASES.get(key)


def normalize_light_target(raw_target: Any) -> str | None:
    target = normalize_device_target(raw_target)
    if target in LIGHT_TARGETS:
        return target
    return None


class ToolRegistry:
    """
    Holds tool definitions (JSON schemas for the LLM) and tool executors.
    """

    def __init__(self, mqtt: MQTTService) -> None:
        self.mqtt = mqtt
        self.executors: dict[str, Any] = {}
        self.definitions: list[dict] = []
        self.register_builtins()

    def execute(self, name: str, args: dict) -> str:
        fn = self.executors.get(name)
        if fn is None:
            return f"Unknown tool: {name}"
        return fn(args)

    def get_definitions(self, names: list[str] | None = None) -> list[dict]:
        """Return tool schemas, optionally filtered by name list."""
        if names is None:
            return list(self.definitions)
        name_set = set(names)
        return [d for d in self.definitions if d["function"]["name"] in name_set]

    def register(self, name: str, desc: str, executor, params=None) -> None:
        self.definitions.append(make_tool_def(name, desc, params))
        self.executors[name] = executor

    def get_device_status_report(self) -> dict:
        devices = self.mqtt.get_device_snapshot()
        return {
            "main_led": devices.get("led_status"),
            "neo_led": devices.get("neo_led_status"),
            "ws2812": devices.get("ws2812_status"),
            "relay": devices.get("relay_status"),
            "mini_fan": devices.get("mini_fan_status"),
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
            devices[device_key] = state
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

    @staticmethod
    def format_device_control_result(result: dict) -> str:
        if not result.get("ok"):
            valid = ", ".join(result.get("valid_targets", []))
            return f"Invalid device_target. Use one of: {valid}."

        action = "ON" if result["requested_state"] else "OFF"
        changed = result.get("changed", [])
        unchanged = result.get("unchanged", [])
        if changed and unchanged:
            return (
                f"Turned {', '.join(changed)} {action}. "
                f"Already {action}: {', '.join(unchanged)}."
            )
        if changed:
            return f"Turned {', '.join(changed)} {action}."
        return f"Already {action}: {', '.join(unchanged)}. No command sent."

    def register_builtins(self) -> None:
        mqtt = self.mqtt

        def device_status_report() -> str:
            return json.dumps(self.get_device_status_report(), indent=2)

        def set_device_state(args: dict, state: bool) -> str:
            result = self.control_device_state(args.get("device_target"), state)
            return self.format_device_control_result(result)

        def set_light_state(args: dict, state: bool) -> str:
            target = normalize_light_target(args.get("light_target"))
            if target is None:
                valid = ", ".join(LIGHT_TARGETS)
                return f"Invalid light_target. Use one of: {valid}."
            return set_device_state({"device_target": target}, state)

        self.register(
            "get_device_status",
            "Get current device states before deciding whether to control a "
            "device. Returns main_led, neo_led, ws2812, relay, and mini_fan "
            "states as true, false, or null if telemetry has not arrived yet.",
            lambda args: device_status_report(),
        )
        self.register(
            "turn_on_device",
            "Turn ON a device only when needed. If the target is already ON, "
            "the executor will not send a duplicate command.",
            lambda args: set_device_state(args, True),
            DEVICE_TOOL_PARAMS,
        )
        self.register(
            "turn_off_device",
            "Turn OFF a device only when needed. If the target is already OFF, "
            "the executor will not send a duplicate command.",
            lambda args: set_device_state(args, False),
            DEVICE_TOOL_PARAMS,
        )

        self.register(
            "turn_on_light",
            "Turn ON one light or all lights. Use light_target="
            "main_led, neo_led, or all_lights.",
            lambda args: set_light_state(args, True),
            LIGHT_TOOL_PARAMS,
        )
        self.register(
            "turn_off_light",
            "Turn OFF one light or all lights. Use light_target="
            "main_led, neo_led, or all_lights.",
            lambda args: set_light_state(args, False),
            LIGHT_TOOL_PARAMS,
        )

        # Legacy aliases kept as executors for backward compatibility.
        self.executors["turn_on_led"] = (
            lambda args: set_device_state({"device_target": "main_led"}, True)
        )
        self.executors["turn_off_led"] = (
            lambda args: set_device_state({"device_target": "main_led"}, False)
        )
        self.executors["turn_on_neo_led"] = (
            lambda args: set_device_state({"device_target": "neo_led"}, True)
        )
        self.executors["turn_off_neo_led"] = (
            lambda args: set_device_state({"device_target": "neo_led"}, False)
        )
        self.executors["turn_on_all_lights"] = (
            lambda args: set_device_state({"device_target": "all_lights"}, True)
        )
        self.executors["turn_off_all_lights"] = (
            lambda args: set_device_state({"device_target": "all_lights"}, False)
        )
        self.executors["turn_on_fan"] = (
            lambda args: set_device_state({"device_target": "mini_fan"}, True)
        )
        self.executors["turn_off_fan"] = (
            lambda args: set_device_state({"device_target": "mini_fan"}, False)
        )

        def get_status(args: dict) -> str:
            return json.dumps(mqtt.get_sensor_snapshot(), indent=2)

        self.register(
            "get_sensor_status",
            "Get current sensor readings: temperature, humidity, "
            "anomaly score, and LED states.",
            get_status,
        )
