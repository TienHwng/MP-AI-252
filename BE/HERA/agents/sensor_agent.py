"""
Sensor Analysis Agent
=====================
Builds a structured sensor report for the orchestrator.
"""

from __future__ import annotations

import json

from agents.base import AgentBase
from core.llm_service import LLMService
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService
from core.tool_registry import ToolRegistry
from config import (
    NORMAL_TEMP_MIN,
    NORMAL_TEMP_MAX,
    NORMAL_HUMI_MIN,
    NORMAL_HUMI_MAX,
    ANOMALY_THRESHOLD,
)

class SensorAnalysisAgent(AgentBase):
    def __init__(
        self, llm: LLMService, mqtt: MQTTService, tools: ToolRegistry,
    ) -> None:
        self.llm = llm
        self.mqtt = mqtt
        self.tools = tools

    @property
    def name(self) -> str:
        return "sensor_analysis"

    @property
    def description(self) -> str:
        return "Answers questions about sensor readings (temperature, humidity, anomaly)."

    async def process(
        self, message: UserMessage, context: dict,
    ) -> AgentResponse:
        snapshot = self.mqtt.get_sensor_snapshot()
        sensors = snapshot.get("sensors", {})
        report = {
            "user_message": message.text,
            "snapshot": snapshot,
            "reference": {
                "temperature_c": {
                    "min": NORMAL_TEMP_MIN,
                    "max": NORMAL_TEMP_MAX,
                },
                "humidity_percent": {
                    "min": NORMAL_HUMI_MIN,
                    "max": NORMAL_HUMI_MAX,
                },
                "anomaly_threshold": ANOMALY_THRESHOLD,
            },
            "status": {
                "temperature_available": sensors.get("temperature") is not None,
                "humidity_available": sensors.get("humidity") is not None,
                "light_available": sensors.get("light") is not None,
                "anomaly_available": sensors.get("anomaly") is not None,
            },
        }
        print("  [SensorAgent] report=sensor_snapshot")

        return AgentResponse(
            text=json.dumps(report, ensure_ascii=False),
            agent_name=self.name,
            tools_used=["get_sensor_status"],
            metadata=report,
        )
