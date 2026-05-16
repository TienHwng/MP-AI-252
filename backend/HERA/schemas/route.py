"""Routing contracts for HERA orchestration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IntentName = Literal[
	"device_control",
	"sensor_query",
	"anomaly_query",
	"web_search",
	"general",
]
RiskLevel = Literal["low", "medium", "high"]


class RouteDecision(BaseModel):
	"""Explicit routing decision produced by the orchestrator."""

	model_config = ConfigDict(extra="forbid")

	intent: IntentName
	specialist: str
	requires_execution: bool
	risk_level: RiskLevel
	clarification_needed: bool = False
	clarification_reason: str | None = None
	capability_scope: list[str] = Field(default_factory=list)
	max_tool_steps: int = 1

	@classmethod
	def from_intent(cls, intent: str, max_tool_steps: int) -> RouteDecision:
		if intent == "device_control":
			return cls(
				intent="device_control",
				specialist="device_control",
				requires_execution=True,
				risk_level="medium",
				capability_scope=[
					"get_device_status",
					"turn_on_device",
					"turn_off_device",
					"set_device_value",
					"set_sensor_value",
				],
				max_tool_steps=max_tool_steps,
			)
		if intent == "sensor_query":
			return cls(
				intent="sensor_query",
				specialist="telemetry_report",
				requires_execution=False,
				risk_level="low",
				capability_scope=["get_current_telemetry"],
				max_tool_steps=1,
			)
		if intent == "anomaly_query":
			return cls(
				intent="anomaly_query",
				specialist="anomaly_analyzer",
				requires_execution=False,
				risk_level="low",
				capability_scope=["analyze_anomaly"],
				max_tool_steps=1,
			)
		if intent == "web_search":
			return cls(
				intent="web_search",
				specialist="web_research",
				requires_execution=False,
				risk_level="low",
				capability_scope=["web_search", "web_fetch"],
				max_tool_steps=1,
			)
		return cls(
			intent="general",
			specialist="orchestrator",
			requires_execution=False,
			risk_level="low",
			capability_scope=[],
			max_tool_steps=1,
		)
