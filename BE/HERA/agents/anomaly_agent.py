"""
Anomaly Expert Agent
====================
Specialised in interpreting anomaly scores from the on-device TinyML model.
Builds a rule-based anomaly report for the orchestrator.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from config import (
	ANOMALY_CRITICAL_THRESHOLD,
	ANOMALY_TELEMETRY_POINT_LIMIT,
	ANOMALY_TELEMETRY_WINDOW_MINUTES,
	ANOMALY_THRESHOLD,
	NORMAL_HUMI_MAX,
	NORMAL_HUMI_MIN,
	NORMAL_TEMP_MAX,
	NORMAL_TEMP_MIN,
	TELEMETRY_STALE_SECONDS,
)
from core.llm_service import LLMService
from core.logger import log_agent
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService
from schemas import SpecialistReport
from telemetry import TelemetryStore, sensor_value

# ── Rule engine ───────────────────────────────────────────────


def compute_telemetry_freshness(sensor: dict) -> dict:
	"""Validate whether the MQTT snapshot is recent enough to trust."""
	last_seen_at = sensor.get("last_seen_at")
	result = {
		"available": bool(last_seen_at),
		"last_seen_at": last_seen_at,
		"age_seconds": None,
		"is_stale": True,
		"stale_after_seconds": TELEMETRY_STALE_SECONDS,
	}
	if not last_seen_at:
		result["reason"] = "missing_last_seen_at"
		return result

	try:
		observed_at = datetime.fromisoformat(str(last_seen_at).replace("Z", "+00:00"))
		if observed_at.tzinfo is None:
			observed_at = observed_at.replace(tzinfo=UTC)
	except ValueError:
		result["reason"] = "invalid_last_seen_at"
		return result

	age_seconds = max(0.0, (datetime.now(UTC) - observed_at).total_seconds())
	result["age_seconds"] = round(age_seconds, 2)
	result["is_stale"] = age_seconds > TELEMETRY_STALE_SECONDS
	result["reason"] = "stale" if result["is_stale"] else "fresh"
	return result


def classify_anomaly(sensor: dict, freshness: dict | None = None) -> dict:
	"""Lightweight rule-based classification (runs before LLM)."""
	if freshness and freshness.get("is_stale"):
		age = freshness.get("age_seconds")
		age_text = "unknown age" if age is None else f"{age:.1f}s old"
		return {
			"type": "stale_telemetry",
			"severity": "unknown",
			"detail": (
				"Latest telemetry is stale or missing "
				f"({age_text}; stale after {TELEMETRY_STALE_SECONDS}s). "
				"Do not make a confident current-state anomaly conclusion."
			),
		}

	sensors = sensor.get("sensors", {})
	temp = sensor_value(sensors, "temperature")
	humi = sensor_value(sensors, "humidity")
	score = sensor_value(sensors, "anomaly")

	if temp is None or humi is None or score is None:
		return {
			"type": "unknown",
			"severity": "none",
			"detail": "Sensor data not yet available.",
		}

	anomaly_type = "normal"
	severity = "none"
	details: list[str] = []

	if temp > NORMAL_TEMP_MAX:
		anomaly_type = "high_temp"
		details.append(f"Temperature is {temp:.1f}°C (above {NORMAL_TEMP_MAX:g}°C).")
	elif temp < NORMAL_TEMP_MIN:
		anomaly_type = "low_temp"
		details.append(f"Temperature is {temp:.1f}°C (below {NORMAL_TEMP_MIN:g}°C).")

	if humi > NORMAL_HUMI_MAX:
		anomaly_type = anomaly_type if anomaly_type != "normal" else "high_humid"
		details.append(f"Humidity is {humi:.1f}% (above {NORMAL_HUMI_MAX:g}%).")
	elif humi < NORMAL_HUMI_MIN:
		anomaly_type = anomaly_type if anomaly_type != "normal" else "low_humid"
		details.append(f"Humidity is {humi:.1f}% (below {NORMAL_HUMI_MIN:g}%).")

	if score > ANOMALY_THRESHOLD:
		severity = "high" if score > ANOMALY_CRITICAL_THRESHOLD else "medium"

		if not details:
			anomaly_type = "ml_detected"
			details.append(
				f"ML anomaly score is {score:.2f} but readings "
				"appear within static thresholds; possible pattern-based anomaly."
			)
	elif details:
		severity = "low"
		details.append(
			f"ML anomaly score is {score:.2f}, below the anomaly threshold "
			f"{ANOMALY_THRESHOLD:g}."
		)

	return {
		"type": anomaly_type,
		"severity": severity,
		"score": score,
		"detail": " ".join(details) if details else "All readings within normal range.",
	}


class AnomalyExpertAgent:
	def __init__(
		self,
		llm: LLMService,
		mqtt: MQTTService,
		telemetry_store: TelemetryStore | None = None,
	) -> None:
		self.llm = llm
		self.mqtt = mqtt
		self.telemetry_store = telemetry_store

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
		freshness = compute_telemetry_freshness(snapshot)
		classification = classify_anomaly(snapshot, freshness)
		telemetry_window = self._recent_telemetry_window(context)
		report = {
			"user_message": message.text,
			"tool_calls": [
				{
					"name": "get_current_telemetry",
					"args": {},
					"confidence": 1.0,
					"source": "anomaly_subgraph",
				}
			],
			"tool_results": [
				{
					"name": "get_current_telemetry",
					"ok": True,
					"result": snapshot,
				},
				{
					"name": "get_telemetry_window",
					"ok": bool(telemetry_window.get("available")),
					"result": telemetry_window,
				},
			],
			"snapshot": snapshot,
			"freshness": freshness,
			"telemetry_window": telemetry_window,
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
				"telemetry_stale_seconds": TELEMETRY_STALE_SECONDS,
				"telemetry_window_minutes": ANOMALY_TELEMETRY_WINDOW_MINUTES,
				"telemetry_point_limit": ANOMALY_TELEMETRY_POINT_LIMIT,
			},
		}
		analysis_payload = dict(report)
		specialist_report = SpecialistReport(
			specialist_name=self.name,
			summary=(
				f"anomaly_type={classification['type']} "
				f"severity={classification['severity']} "
				f"freshness={freshness['reason']} "
				f"window_points={telemetry_window.get('point_count', 0)}"
			),
			analysis_payload=analysis_payload,
		)
		report["specialist_report"] = specialist_report.model_dump(mode="json")
		log_agent(
			f"AnomalyExpert: type={classification['type']} severity={classification['severity']}",
			data={
				"freshness": freshness["reason"],
				"age_s": freshness["age_seconds"],
				"window_pts": telemetry_window.get("point_count", 0),
				"score": classification.get("score"),
			},
		)

		return AgentResponse(
			text=json.dumps(report, ensure_ascii=False),
			agent_name=self.name,
			metadata=report,
		)

	def _recent_telemetry_window(self, context: dict) -> dict:
		if self.telemetry_store is None:
			return {"available": False, "reason": "telemetry_store_not_configured"}
		request = context.get("incoming_request")
		user_id = getattr(request, "user_id", None)
		return self.telemetry_store.recent_summary(
			user_id=user_id,
			window_minutes=ANOMALY_TELEMETRY_WINDOW_MINUTES,
			limit=ANOMALY_TELEMETRY_POINT_LIMIT,
		)
