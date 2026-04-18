"""
Anomaly Expert Agent
====================
Specialised in interpreting anomaly scores from the on-device TinyML model.
Builds a rule-based anomaly report for the orchestrator.
"""

from __future__ import annotations

import json

from config import (
	ANOMALY_CRITICAL_THRESHOLD,
	ANOMALY_THRESHOLD,
	NORMAL_HUMI_MAX,
	NORMAL_HUMI_MIN,
	NORMAL_TEMP_MAX,
	NORMAL_TEMP_MIN,
)
from core.llm_service import LLMService
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService

from agents.base import AgentBase

# ── Rule engine ───────────────────────────────────────────────


def classify_anomaly(sensor: dict) -> dict:
	"""Lightweight rule-based classification (runs before LLM)."""
	sensors = sensor.get("sensors", {})
	temp = sensors.get("temperature")
	humi = sensors.get("humidity")
	score = sensors.get("anomaly")

	if temp is None or humi is None or score is None:
		return {
			"type": "unknown",
			"severity": "none",
			"detail": "Sensor data not yet available.",
		}

	anomaly_type = "normal"
	severity = "none"
	details: list[str] = []

	if score > ANOMALY_THRESHOLD:
		severity = "high" if score > ANOMALY_CRITICAL_THRESHOLD else "medium"

		if temp > NORMAL_TEMP_MAX:
			anomaly_type = "high_temp"
			details.append(
				f"Temperature is {temp:.1f}°C (above {NORMAL_TEMP_MAX:g}°C)."
			)
		elif temp < NORMAL_TEMP_MIN:
			anomaly_type = "low_temp"
			details.append(
				f"Temperature is {temp:.1f}°C (below {NORMAL_TEMP_MIN:g}°C)."
			)

		if humi > NORMAL_HUMI_MAX:
			anomaly_type = anomaly_type if anomaly_type != "normal" else "high_humid"
			details.append(f"Humidity is {humi:.1f}% (above {NORMAL_HUMI_MAX:g}%).")
		elif humi < NORMAL_HUMI_MIN:
			anomaly_type = anomaly_type if anomaly_type != "normal" else "low_humid"
			details.append(f"Humidity is {humi:.1f}% (below {NORMAL_HUMI_MIN:g}%).")

		if not details:
			anomaly_type = "ml_detected"
			details.append(
				f"ML anomaly score is {score:.2f} but readings "
				"appear within static thresholds; possible pattern-based anomaly."
			)

	return {
		"type": anomaly_type,
		"severity": severity,
		"score": score,
		"detail": " ".join(details) if details else "All readings within normal range.",
	}


class AnomalyExpertAgent(AgentBase):
	def __init__(self, llm: LLMService, mqtt: MQTTService) -> None:
		self.llm = llm
		self.mqtt = mqtt

	@property
	def name(self) -> str:
		return "anomaly_expert"

	@property
	def description(self) -> str:
		return "Explains anomaly detections — causes, severity, recommendations."

	async def process(
		self,
		message: UserMessage,
		context: dict,
	) -> AgentResponse:
		snapshot = self.mqtt.get_sensor_snapshot()
		classification = classify_anomaly(snapshot)
		report = {
			"user_message": message.text,
			"snapshot": snapshot,
			"classification": classification,
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
				"anomaly_critical_threshold": ANOMALY_CRITICAL_THRESHOLD,
			},
		}
		print(
			f"  [AnomalyAgent] type={classification['type']} severity={classification['severity']}"
		)

		return AgentResponse(
			text=json.dumps(report, ensure_ascii=False),
			agent_name=self.name,
			metadata=report,
		)
