"""
Sensor Analysis Agent
=====================
Answers questions about current and (future) historical sensor data.
Uses get_sensor_status tool + LLM reasoning to interpret readings.
"""

from __future__ import annotations

import asyncio
import json

from agents.base import AgentBase
from core.llm_service import LLMService, filter_response
from core.language_policy import build_language_policy, enforce_language_output
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService
from core.tool_registry import ToolRegistry
from config import (
    MAX_TOOL_ITERATIONS,
    NORMAL_TEMP_MIN,
    NORMAL_TEMP_MAX,
    NORMAL_HUMI_MIN,
    NORMAL_HUMI_MAX,
    ANOMALY_THRESHOLD,
    SENSOR_AGENT_MODEL_OLLAMA,
    SENSOR_AGENT_MODEL_OPENROUTER,
)

SYSTEM_PROMPT = """\
You are the Sensor Analysis module of HERA, an IoT environmental monitor.

### Live sensor data
{sensor_context}

### Reference values
- Normal temperature: 25–35 °C
- Normal humidity: 60–80 %
- Anomaly score > 0.5 = abnormal (on-device ML)

### Rules
- ALWAYS respond in the SAME LANGUAGE as the user
- Use get_sensor_status if you need fresh data
- Interpret readings: explain if values are normal/abnormal
- Be concise and data-driven
- NEVER output Chinese/Mandarin
"""


class SensorAnalysisAgent(AgentBase):
    def __init__(
        self, llm: LLMService, mqtt: MQTTService, tools: ToolRegistry,
    ) -> None:
        self._llm = llm
        self._mqtt = mqtt
        self._tools = tools
        self._model_override = (
            SENSOR_AGENT_MODEL_OLLAMA
            if llm.provider == "ollama"
            else SENSOR_AGENT_MODEL_OPENROUTER
        )

    @property
    def name(self) -> str:
        return "sensor_analysis"

    @property
    def description(self) -> str:
        return "Answers questions about sensor readings (temperature, humidity, anomaly)."

    async def process(
        self, message: UserMessage, context: dict,
    ) -> AgentResponse:
        target_language = context.get("target_language", "en")
        sensor_ctx = json.dumps(self._mqtt.get_sensor_snapshot(), indent=2)
        tool_defs = self._tools.get_definitions(["get_sensor_status"])
        system_prompt = (
            SYSTEM_PROMPT.format(sensor_context=sensor_ctx)
            .replace("25–35", f"{NORMAL_TEMP_MIN:g}-{NORMAL_TEMP_MAX:g}")
            .replace("60–80", f"{NORMAL_HUMI_MIN:g}-{NORMAL_HUMI_MAX:g}")
            .replace("> 0.5", f"> {ANOMALY_THRESHOLD:g}")
            + "\n\n"
            + build_language_policy(target_language)
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message.text},
        ]

        tools_used: list[str] = []

        for _ in range(MAX_TOOL_ITERATIONS):
            result = await asyncio.to_thread(
                self._llm.completion, messages, tool_defs, self._model_override,
            )
            if not result["tool_calls"]:
                reply = result["content"] or "(no response)"
                break

            messages.append(
                self._llm.build_assistant_tool_msg(
                    result["content"], result["tool_calls"],
                )
            )
            for tc in result["tool_calls"]:
                print(f"  [SensorAgent] 📊 {tc['name']}")
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
