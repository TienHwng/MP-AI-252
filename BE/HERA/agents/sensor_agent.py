"""
Sensor Analysis Agent
=====================
Builds a structured sensor report for the orchestrator.
"""

from __future__ import annotations

import json

from config import (
	ANOMALY_THRESHOLD,
	NORMAL_HUMI_MAX,
	NORMAL_HUMI_MIN,
	NORMAL_TEMP_MAX,
	NORMAL_TEMP_MIN,
)
from core.llm_service import LLMService
from core.logger import log_agent
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService
from core.tool_registry import ToolRegistry
from schemas import SpecialistReport
from telemetry import sensor_value


class SensorAnalysisAgent:
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
		return "sensor_analysis"

	@property
	def description(self) -> str:
		return (
			"Answers questions about sensor readings (temperature, humidity, anomaly)."
		)

	async def process(
		self,
		message: UserMessage,
		context: dict,
	) -> AgentResponse:
		snapshot = self.mqtt.get_sensor_snapshot()
		sensors = snapshot.get("sensors", {})
		report = {
			"user_message": message.text,
			"tool_calls": [
				{
					"name": "get_current_telemetry",
					"args": {},
					"confidence": 1.0,
					"source": "sensor_subgraph",
				}
			],
			"tool_results": [
				{
					"name": "get_current_telemetry",
					"ok": True,
					"result": snapshot,
				}
			],
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
				"temperature_available": sensor_value(sensors, "temperature") is not None,
				"humidity_available": sensor_value(sensors, "humidity") is not None,
				"light_available": sensor_value(sensors, "light") is not None,
				"anomaly_available": sensor_value(sensors, "anomaly") is not None,
			},
		}
		analysis_payload = dict(report)
		specialist_report = SpecialistReport(
			specialist_name=self.name,
			summary="sensor_snapshot_report",
			tool_proposals=[],
			analysis_payload=analysis_payload,
		)
		report["specialist_report"] = specialist_report.model_dump(mode="json")
		temp = sensor_value(sensors, "temperature")
		humi = sensor_value(sensors, "humidity")
		log_agent(
			"SensorAnalysis: snapshot ready",
			data={
				"temp": f"{temp:.1f}°C" if isinstance(temp, (int, float)) else "N/A",
				"humi": f"{humi:.1f}%" if isinstance(humi, (int, float)) else "N/A",
				"light": sensor_value(sensors, "light"),
				"anomaly": sensor_value(sensors, "anomaly"),
			},
		)

		return AgentResponse(
			text=json.dumps(report, ensure_ascii=False),
			agent_name=self.name,
			metadata=report,
		)
