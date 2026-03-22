"""
Anomaly Expert Agent
====================
Specialised in interpreting anomaly scores from the on-device TinyML model.
Combines rule-based severity assessment with LLM explanation.
"""

from __future__ import annotations

import asyncio
import json

from agents.base import AgentBase
from core.llm_service import LLMService, filter_response
from core.language_policy import build_language_policy, enforce_language_output
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService
from config import (
    NORMAL_TEMP_MIN,
    NORMAL_TEMP_MAX,
    NORMAL_HUMI_MIN,
    NORMAL_HUMI_MAX,
    ANOMALY_THRESHOLD,
    ANOMALY_CRITICAL_THRESHOLD,
    ANOMALY_AGENT_MODEL_OLLAMA,
    ANOMALY_AGENT_MODEL_OPENROUTER,
)

# ── Rule engine ───────────────────────────────────────────────

def classify_anomaly(sensor: dict) -> dict:
    """Lightweight rule-based classification (runs before LLM)."""
    temp = sensor.get("temperature")
    humi = sensor.get("humidity")
    score = sensor.get("inference_result")

    if temp is None or humi is None or score is None:
        return {"type": "unknown", "severity": "none",
                "detail": "Sensor data not yet available."}

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
            details.append(
                f"Humidity is {humi:.1f}% (above {NORMAL_HUMI_MAX:g}%)."
            )
        elif humi < NORMAL_HUMI_MIN:
            anomaly_type = anomaly_type if anomaly_type != "normal" else "low_humid"
            details.append(
                f"Humidity is {humi:.1f}% (below {NORMAL_HUMI_MIN:g}%)."
            )

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


SYSTEM_PROMPT = """\
You are the Anomaly Analysis module of HERA, an IoT environmental monitor.

### Current sensor data
{sensor_context}

### Anomaly classification (rule-engine)
{anomaly_context}

### Reference values
- Normal temperature: 25–35 °C
- Normal humidity: 60–80 %
- Anomaly score > 0.5 = abnormal (on-device ML), > 0.8 = critical

### Rules
- ALWAYS respond in the SAME LANGUAGE as the user
- Explain the anomaly in simple terms: what is wrong, possible causes, recommendation
- If severity is high, suggest immediate action
- Be concise and actionable
- NEVER output Chinese/Mandarin
"""


class AnomalyExpertAgent(AgentBase):
    def __init__(self, llm: LLMService, mqtt: MQTTService) -> None:
        self._llm = llm
        self._mqtt = mqtt
        self._model_override = (
            ANOMALY_AGENT_MODEL_OLLAMA
            if llm.provider == "ollama"
            else ANOMALY_AGENT_MODEL_OPENROUTER
        )

    @property
    def name(self) -> str:
        return "anomaly_expert"

    @property
    def description(self) -> str:
        return "Explains anomaly detections — causes, severity, recommendations."

    async def process(
        self, message: UserMessage, context: dict,
    ) -> AgentResponse:
        target_language = context.get("target_language", "en")
        snapshot = self._mqtt.get_sensor_snapshot()
        classification = classify_anomaly(snapshot)
        system_prompt = (
            SYSTEM_PROMPT.format(
                sensor_context=json.dumps(snapshot, indent=2),
                anomaly_context=json.dumps(classification, indent=2),
            )
            .replace("25–35", f"{NORMAL_TEMP_MIN:g}-{NORMAL_TEMP_MAX:g}")
            .replace("60–80", f"{NORMAL_HUMI_MIN:g}-{NORMAL_HUMI_MAX:g}")
            .replace("> 0.5", f"> {ANOMALY_THRESHOLD:g}")
            .replace("> 0.8", f"> {ANOMALY_CRITICAL_THRESHOLD:g}")
            + "\n\n"
            + build_language_policy(target_language)
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message.text},
        ]

        result = await asyncio.to_thread(
            self._llm.completion, messages, None, self._model_override,
        )
        reply = enforce_language_output(
            filter_response(result["content"] or "(no analysis)"),
            target_language,
        )

        return AgentResponse(
            text=reply,
            agent_name=self.name,
            metadata={"anomaly": classification},
        )
