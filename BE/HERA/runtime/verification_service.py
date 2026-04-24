"""Verification checks after tool execution."""

from __future__ import annotations

from domain.devices import DEVICE_STATUS_KEYS
from schemas import (
	PolicyDecision,
	ToolExecutionResult,
	ToolProposal,
	VerificationResult,
)

DEVICE_NAME_BY_STATUS_KEY = {
	status_key: device_name for device_name, status_key in DEVICE_STATUS_KEYS.items()
}


class VerificationService:
	"""Verifies execution outcomes against cached device state."""

	def verify(
		self,
		proposal: ToolProposal,
		execution_result: ToolExecutionResult,
		policy_decision: PolicyDecision,
	) -> VerificationResult:
		if policy_decision.decision in {"ask", "deny"}:
			return VerificationResult(
				status="rejected",
				source="policy",
				confidence=1.0,
				details={
					"policy_decision": policy_decision.model_dump(mode="json"),
				},
			)

		if policy_decision.decision == "noop":
			return VerificationResult(
				status="noop",
				source="cached_state",
				confidence=1.0,
				details={
					"reason": policy_decision.reason,
				},
			)

		if execution_result.status == "status_requested":
			return VerificationResult(
				status="verified",
				source="cached_state",
				confidence=1.0,
				details={"reason": "read_only_status_request"},
			)

		if not execution_result.ok:
			return VerificationResult(
				status="failed",
				source="none",
				confidence=0.8,
				details={"reason": execution_result.reason},
			)

		commands_sent = execution_result.raw_metadata.get("commands_sent", [])
		if not commands_sent:
			return VerificationResult(
				status="noop",
				source="cached_state",
				confidence=1.0,
				details={"reason": execution_result.reason},
			)

		after_state = execution_result.after_state
		if not after_state:
			return VerificationResult(
				status="unverified",
				source="none",
				confidence=0.0,
				details={"reason": "missing_after_state"},
			)

		mismatches: list[dict] = []
		for command in commands_sent:
			device_key = command.get("device_key")
			device_name = DEVICE_NAME_BY_STATUS_KEY.get(device_key)
			if device_name is None:
				mismatches.append(
					{
						"device_key": device_key,
						"reason": "unknown_device_key",
					}
				)
				continue

			expected = command.get("params")
			observed = after_state.get(device_name)
			if observed is not expected:
				mismatches.append(
					{
						"device": device_name,
						"expected": expected,
						"observed": observed,
					}
				)

		if mismatches:
			if execution_result.raw_metadata.get("double_check_timed_out"):
				return VerificationResult(
					status="timeout",
					source="state_readback",
					confidence=0.3,
					details={
						"reason": "state_readback_timeout",
						"mismatches": mismatches,
					},
				)
			return VerificationResult(
				status="failed",
				source="state_readback",
				confidence=0.9,
				details={"mismatches": mismatches},
			)

		return VerificationResult(
			status="verified",
			source="state_readback",
			confidence=0.9,
			details={
				"commands_checked": len(commands_sent),
				"capability_name": proposal.capability_name,
			},
		)
