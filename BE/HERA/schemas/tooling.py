"""Tooling, policy, execution, and verification contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PolicyOutcome = Literal["allow", "deny", "ask", "modify", "noop"]
VerificationStatus = Literal[
	"verified",
	"unverified",
	"failed",
	"stale",
	"unknown",
	"timeout",
	"rejected",
	"noop",
	"offline",
]
VerificationSource = Literal[
	"mqtt_ack",
	"state_readback",
	"telemetry_window",
	"cached_state",
	"policy",
	"none",
]


class CapabilitySpec(BaseModel):
	"""Declarative capability metadata for future policy/runtime separation."""

	model_config = ConfigDict(extra="forbid")

	name: str
	description: str
	parameters: dict[str, Any] = Field(default_factory=dict)
	effect_type: Literal["read", "write"]
	risk_level: Literal["low", "medium", "high"]
	timeout_ms: int = 3000
	supports_idempotency: bool = True
	requires_confirmation: bool = False
	verifier_name: str | None = None


class ToolProposal(BaseModel):
	"""A specialist proposal; later phases will execute these centrally."""

	model_config = ConfigDict(extra="forbid")

	capability_name: str
	arguments: dict[str, Any] = Field(default_factory=dict)
	rationale: str
	expected_outcome: str
	confidence: float = Field(ge=0.0, le=1.0)
	ambiguity_detected: bool = False
	clarification_question: str | None = None


class PolicyDecision(BaseModel):
	"""Policy output richer than allow/deny."""

	model_config = ConfigDict(extra="forbid")

	decision: PolicyOutcome
	reason: str
	user_visible_message: str | None = None
	modified_arguments: dict[str, Any] | None = None


class VerificationResult(BaseModel):
	"""Result of checking whether an action actually took effect."""

	model_config = ConfigDict(extra="forbid")

	status: VerificationStatus
	source: VerificationSource
	confidence: float = Field(ge=0.0, le=1.0)
	details: dict[str, Any] = Field(default_factory=dict)

	@classmethod
	def not_checked(cls, details: dict[str, Any] | None = None) -> VerificationResult:
		return cls(
			status="unknown",
			source="none",
			confidence=0.0,
			details=details or {},
		)


class ToolExecutionResult(BaseModel):
	"""Standard contract for results from effectful tool execution."""

	model_config = ConfigDict(extra="forbid")

	ok: bool
	capability_name: str
	status: str
	reason: str
	changed_entities: list[str] = Field(default_factory=list)
	unchanged_entities: list[str] = Field(default_factory=list)
	failed_entities: list[str] = Field(default_factory=list)
	before_state: dict[str, Any] = Field(default_factory=dict)
	after_state: dict[str, Any] = Field(default_factory=dict)
	verification: VerificationResult = Field(
		default_factory=VerificationResult.not_checked
	)
	policy_decision: PolicyDecision | None = None
	raw_metadata: dict[str, Any] = Field(default_factory=dict)

	@classmethod
	def from_device_result(
		cls,
		*,
		capability_name: str,
		result: dict[str, Any],
	) -> ToolExecutionResult:
		before_state = result.get("states_before")
		if not isinstance(before_state, dict):
			before_state = {}

		after_state = result.get("states_after") or result.get("device_status")
		if not isinstance(after_state, dict):
			after_state = {}

		failed_entities: list[str] = []
		if not result.get("ok"):
			target = result.get("target")
			failed_entities = [str(target)] if target is not None else []

		return cls(
			ok=bool(result.get("ok")),
			capability_name=capability_name,
			status=str(result.get("reason", "unknown")),
			reason=str(result.get("reason", "unknown")),
			changed_entities=[str(item) for item in result.get("changed", [])],
			unchanged_entities=[str(item) for item in result.get("unchanged", [])],
			failed_entities=failed_entities,
			before_state=before_state,
			after_state=after_state,
			verification=VerificationResult.not_checked(
				{
					"phase": "phase_2_runtime_separation",
					"note": "Execution used central runtime; no verifier override was supplied.",
				}
			),
			raw_metadata=dict(result),
		)

	@classmethod
	def from_device_registry_result(
		cls,
		*,
		capability_name: str,
		result: dict[str, Any],
	) -> ToolExecutionResult:
		return cls.from_device_result(
			capability_name=capability_name,
			result=result,
		)
