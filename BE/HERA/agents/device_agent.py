"""
Device Control Agent
====================
Handles LED and actuator commands via tool calling.
Uses the smallest feasible model because the task is highly constrained.
"""

from __future__ import annotations

import asyncio

from agents.base import AgentBase
from core.llm_service import LLMService, filter_response
from core.language_policy import build_language_policy, enforce_language_output
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService
from core.tool_registry import ToolRegistry
from config import (
    MAX_TOOL_ITERATIONS,
    DEVICE_AGENT_MODEL_OLLAMA,
    DEVICE_AGENT_MODEL_OPENROUTER,
)

_DEVICE_TOOLS = [
    "turn_on_light",
    "turn_off_light",
]

SYSTEM_PROMPT = """\
You are the Device Control module of HERA, an IoT assistant.
Your ONLY job is to control the two LEDs on an ESP32 device.

### Two LEDs
1. White Indicator LED (main LED)
2. NeoPixel RGB LED (colorful LED)

### Rules
- ALWAYS respond in the SAME LANGUAGE as the user
- Call the appropriate tool(s) to fulfil the request
- After execution, confirm briefly (one sentence)
- Use `turn_on_light` or `turn_off_light`
- Set `light_target` to `main_led`, `neo_led`, or `all_lights`
- "lights" / "both" / "all" means `all_lights`
- White / indicator LED means `main_led`
- NeoPixel / RGB / colorful LED means `neo_led`
- DO NOT answer questions unrelated to device control
- NEVER output Chinese/Mandarin
"""


class DeviceControlAgent(AgentBase):
    def __init__(
        self, llm: LLMService, mqtt: MQTTService, tools: ToolRegistry,
    ) -> None:
        self._llm = llm
        self._mqtt = mqtt
        self._tools = tools
        if llm.provider == "ollama":
            self._model_override = DEVICE_AGENT_MODEL_OLLAMA
        else:
            self._model_override = DEVICE_AGENT_MODEL_OPENROUTER

    @property
    def name(self) -> str:
        return "device_control"

    @property
    def description(self) -> str:
        return "Controls LEDs and actuators on the ESP32 device."

    async def process(
        self, message: UserMessage, context: dict,
    ) -> AgentResponse:
        target_language = context.get("target_language", "en")
        tool_defs = self._tools.get_definitions(_DEVICE_TOOLS)
        system_prompt = (
            f"{SYSTEM_PROMPT}\n\n{build_language_policy(target_language)}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message.text},
        ]

        tools_used: list[str] = []

        for _ in range(MAX_TOOL_ITERATIONS):
            result = await asyncio.to_thread(
                self._llm.completion,
                messages,
                tool_defs,
                self._model_override,
            )

            if not result["tool_calls"]:
                reply = result["content"] or "Done."
                break

            messages.append(
                self._llm.build_assistant_tool_msg(
                    result["content"],
                    result["tool_calls"],
                )
            )
            for tc in result["tool_calls"]:
                print(f"  [DeviceAgent] {tc['name']}({tc['args']})")
                tool_result = self._tools.execute(tc["name"], tc["args"])
                tools_used.append(tc["name"])
                messages.append(
                    self._llm.build_tool_result_msg(tc["id"], tool_result),
                )
        else:
            reply = "Reached tool-call limit."

        return AgentResponse(
            text=enforce_language_output(filter_response(reply), target_language),
            agent_name=self.name,
            tools_used=tools_used,
        )
