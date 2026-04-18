"""
Device Control Agent
====================
Handles actuator commands through a parse -> execute flow.
The orchestrator owns the final user-facing response.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from agents.base import AgentBase
from core.llm_service import LLMService
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService
from core.runtime_settings import runtime_settings
from core.tool_registry import DEVICE_TARGETS, ToolRegistry

COMMAND_PARSER_PROMPT = """\
You are a command parser for HERA's ESP32 actuators.
Return ONLY one valid JSON object. Do not answer the user.

Supported targets:
- main_led: white indicator LED
- neo_led: NeoPixel RGB LED
- ws2812: WS2812 LED strip
- relay: relay
- mini_fan: mini fan / fan / quat / quạt
- all_lights: all LEDs/lights: main_led, neo_led, ws2812
- all_devices: every supported actuator

Supported actions:
- turn_on
- turn_off
- status
- unknown

Rules:
- "đèn", "den", "light", or "lights" without a specific type means all_lights.
- "quạt", "quat", "fan", or "mini fan" means mini_fan.
- If the user asks whether a device is on/off, use action=status.
- If the user asks to keep a device unchanged, do not include that device as
  the target unless it is also the requested control target.
- If the command is ambiguous, use action=unknown and target=null.

Output schema:
{
  "action": "turn_on" | "turn_off" | "status" | "unknown",
  "target": "main_led" | "neo_led" | "ws2812" | "relay" | "mini_fan" | "all_lights" | "all_devices" | null,
  "confidence": 0.0-1.0
}

Do not include any other keys.
Do not output Chinese, Mandarin, Japanese, or Korean text anywhere.
"""


def extract_json_object(raw_text: str | None) -> dict:
	text = (raw_text or "").strip()
	if not text:
		return {}

	if text.startswith("```"):
		text = text.strip("`")
		if "\n" in text:
			text = text.split("\n", 1)[1]

	start = text.find("{")
	end = text.rfind("}")
	if start == -1 or end == -1 or end <= start:
		return {}

	try:
		parsed = json.loads(text[start : end + 1])
	except json.JSONDecodeError:
		return {}
	return parsed if isinstance(parsed, dict) else {}


def normalise_command(parsed: dict[str, Any]) -> dict:
	action = parsed.get("action")
	target = parsed.get("target")
	if action not in {"turn_on", "turn_off", "status", "unknown"}:
		action = "unknown"
	if target not in DEVICE_TARGETS:
		target = None
	if action in {"turn_on", "turn_off", "status"} and target is None:
		action = "unknown"
	return {
		"action": action,
		"target": target,
		"confidence": parsed.get("confidence"),
	}


class DeviceControlAgent(AgentBase):
	def __init__(
		self,
		llm: LLMService,
		mqtt: MQTTService,
		tools: ToolRegistry,
	) -> None:
		self.llm = llm
		self.mqtt = mqtt
		self.tools = tools

	@property
	def name(self) -> str:
		return "device_control"

	@property
	def description(self) -> str:
		return "Controls LEDs and actuators on the ESP32 device."

	async def parse_command(self, message: UserMessage) -> dict:
		model_override = runtime_settings.get_active_model("deviceControlModel")
		device_context = json.dumps(self.tools.get_device_status_report(), indent=2)
		messages = [
			{
				"role": "system",
				"content": (
					COMMAND_PARSER_PROMPT
					+ "\n\nCurrent device snapshot:\n"
					+ device_context
				),
			},
			{"role": "user", "content": message.text},
		]
		result = await asyncio.to_thread(
			self.llm.completion,
			messages,
			None,
			model_override,
		)
		parsed = extract_json_object(result["content"])
		return normalise_command(parsed)

	def execute_command(self, command: dict) -> tuple[dict, list[str]]:
		action = command["action"]
		target = command["target"]

		if action == "turn_on":
			result = self.tools.control_device_state(target, True)
			return result, ["turn_on_device"] if result.get("ok") else []

		if action == "turn_off":
			result = self.tools.control_device_state(target, False)
			return result, ["turn_off_device"] if result.get("ok") else []

		if action == "status":
			return (
				{
					"ok": True,
					"reason": "status_requested",
					"target": target,
					"device_status": self.tools.get_device_status_report(),
					"commands_sent": [],
				},
				["get_device_status"],
			)

		return (
			{
				"ok": False,
				"reason": "unknown_or_ambiguous_command",
				"target": target,
				"device_status": self.tools.get_device_status_report(),
				"commands_sent": [],
			},
			[],
		)

	async def process(
		self,
		message: UserMessage,
		context: dict,
	) -> AgentResponse:
		command = await self.parse_command(message)
		execution_result, tools_used = self.execute_command(command)
		print(f"  [DeviceAgent] action={command['action']} target={command['target']}")

		report = {
			"parsed_command": command,
			"execution_result": execution_result,
		}

		return AgentResponse(
			text=json.dumps(report, ensure_ascii=False),
			agent_name=self.name,
			tools_used=tools_used,
			metadata=report,
		)
