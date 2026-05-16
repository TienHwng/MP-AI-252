"""Current telemetry read/report service for HERA."""

from __future__ import annotations

import json

from config import (
	ANOMALY_THRESHOLD,
	NORMAL_HUMI_MAX,
	NORMAL_HUMI_MIN,
	NORMAL_TEMP_MAX,
	NORMAL_TEMP_MIN,
)
from core.logger import log_telemetry
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService
from schemas import SpecialistReport
from telemetry import sensor_value


class TelemetryReportService:
	"""Builds structured reports from the current MQTT telemetry snapshot."""

	def __init__(self, mqtt: MQTTService, read_tool_runner=None) -> None:
		self.mqtt = mqtt
		self.read_tool_runner = read_tool_runner

	@property
	def name(self) -> str:
		return "telemetry_report"

	@property
	def description(self) -> str:
		return "Reads current temperature, humidity, light, and anomaly telemetry."

	async def process(
		self,
		message: UserMessage,
		context: dict,
	) -> AgentResponse:
		_ = context
		snapshot = self._current_snapshot()
		sensors = snapshot.get("sensors", {})
		report = {
			"user_message": message.text,
			"data_sources": [
				{
					"name": "get_current_telemetry",
					"args": {},
					"confidence": 1.0,
					"source": "telemetry_report_service",
				}
			],
			"data_results": [
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
		log_telemetry(
			"TelemetryReport: snapshot ready",
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

	def _current_snapshot(self) -> dict:
		if self.read_tool_runner is None:
			return self.mqtt.get_sensor_snapshot()
		result = self.read_tool_runner.run("get_current_telemetry")
		snapshot = result.get("result") if isinstance(result, dict) else None
		return snapshot if isinstance(snapshot, dict) else self.mqtt.get_sensor_snapshot()
