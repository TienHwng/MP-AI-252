"""Central execution path for specialist tool proposals."""

from __future__ import annotations

import time
from typing import Any

from config import DEVICE_VERIFICATION_POLL_SECONDS, DEVICE_VERIFICATION_TIMEOUT_SECONDS
from domain.devices.device_executor import DeviceExecutor
from schemas import (
	PolicyDecision,
	ToolExecutionResult,
	ToolProposal,
	VerificationResult,
)

from runtime.capability_registry import CapabilityRegistry
from runtime.execution_context import ExecutionContext
from runtime.policy_engine import PolicyEngine
from runtime.verification_service import VerificationService


class ToolRunner:
	"""Validates proposals and delegates side effects to domain executors."""

	def __init__(
		self,
		capabilities: CapabilityRegistry,
		device_executor: DeviceExecutor,
		policy_engine: PolicyEngine | None = None,
		verification_service: VerificationService | None = None,
	) -> None:
		self.capabilities = capabilities
		self.device_executor = device_executor
		self.policy_engine = policy_engine or PolicyEngine()
		self.verification_service = verification_service or VerificationService()

	def get_device_status_report(self) -> dict:
		return self.device_executor.get_device_status_report()

	def run(
		self,
		proposal: ToolProposal,
		context: ExecutionContext | None = None,
	) -> ToolExecutionResult:
		capability = self.capabilities.get(proposal.capability_name)
		if capability is None:
			return self._rejected_result(
				proposal,
				status="unknown_capability",
				reason=f"Unknown capability: {proposal.capability_name}",
				context=context,
			)

		policy_decision = self.policy_engine.evaluate(
			proposal,
			capability,
			self.device_executor.get_runtime_state(),
		)
		if policy_decision.decision in {"ask", "deny"}:
			return self._policy_result(
				proposal,
				policy_decision,
				context,
				ok=False,
				status=policy_decision.decision,
			)
		if policy_decision.decision == "noop":
			return self._policy_result(
				proposal,
				policy_decision,
				context,
				ok=True,
				status="noop",
			)

		executable_proposal = proposal
		if policy_decision.decision == "modify" and policy_decision.modified_arguments:
			executable_proposal = proposal.model_copy(
				update={"arguments": policy_decision.modified_arguments}
			)

		if executable_proposal.capability_name == "get_device_status":
			result = self.device_executor.get_status_result(
				executable_proposal.arguments.get("device_target")
			)
		elif executable_proposal.capability_name == "turn_on_device":
			result = self._run_device_state(executable_proposal, True)
		elif executable_proposal.capability_name == "turn_off_device":
			result = self._run_device_state(executable_proposal, False)
		else:
			return self._rejected_result(
				executable_proposal,
				status="unsupported_capability",
				reason=f"Capability is declared but not executable yet: {capability.name}",
				context=context,
			)

		execution_result = ToolExecutionResult.from_device_result(
			capability_name=executable_proposal.capability_name,
			result=result,
		)
		execution_result.policy_decision = policy_decision
		self.double_check_device_state(execution_result)
		execution_result.verification = self.verification_service.verify(
			executable_proposal,
			execution_result,
			policy_decision,
		)
		execution_result.raw_metadata["policy_decision"] = policy_decision.model_dump(
			mode="json"
		)
		execution_result.raw_metadata["runtime_context"] = (
			context.model_dump(mode="json") if context else {}
		)
		return execution_result

	def double_check_device_state(self, execution_result: ToolExecutionResult) -> None:
		"""Poll the status snapshot after write commands before verification."""
		commands_sent = execution_result.raw_metadata.get("commands_sent", [])
		if not commands_sent:
			return

		expected = {
			command.get("device_key"): command.get("params")
			for command in commands_sent
			if command.get("device_key") is not None
		}
		if not expected:
			return

		timeout = max(float(DEVICE_VERIFICATION_TIMEOUT_SECONDS), 0.0)
		poll_interval = max(float(DEVICE_VERIFICATION_POLL_SECONDS), 0.0)
		deadline = time.monotonic() + timeout
		status = self.device_executor.get_device_status_report()
		matched = self._status_matches_expected(status, expected)
		while not matched and timeout > 0 and time.monotonic() < deadline:
			remaining = deadline - time.monotonic()
			if remaining <= 0:
				break
			if poll_interval <= 0:
				break
			time.sleep(min(poll_interval, remaining))
			status = self.device_executor.get_device_status_report()
			matched = self._status_matches_expected(status, expected)

		execution_result.after_state = status
		execution_result.raw_metadata["double_check_status"] = status
		execution_result.raw_metadata["double_check_expected"] = expected
		execution_result.raw_metadata["double_check_matched"] = matched
		execution_result.raw_metadata["double_check_timed_out"] = not matched

	@staticmethod
	def _status_matches_expected(status: dict, expected: dict) -> bool:
		status_key_by_name = {
			"main_led": "led_status",
			"neo_led": "neo_led_status",
			"ws2812": "ws2812_status",
			"relay": "relay_status",
			"mini_fan": "mini_fan_status",
		}
		name_by_status_key = {
			status_key: name for name, status_key in status_key_by_name.items()
		}
		for device_key, expected_value in expected.items():
			device_name = name_by_status_key.get(device_key)
			if device_name is None or status.get(device_name) is not expected_value:
				return False
		return True

	def _run_device_state(self, proposal: ToolProposal, requested_state: bool) -> dict:
		target = proposal.arguments.get("device_target")
		if target is None:
			return {
				"ok": False,
				"reason": "missing_device_target",
				"target": None,
				"requested_state": requested_state,
				"commands_sent": [],
			}
		return self.device_executor.control_device_state(target, requested_state)

	@staticmethod
	def _rejected_result(
		proposal: ToolProposal,
		*,
		status: str,
		reason: str,
		context: ExecutionContext | None,
	) -> ToolExecutionResult:
		raw_metadata: dict[str, Any] = {
			"proposal": proposal.model_dump(mode="json"),
			"runtime_context": context.model_dump(mode="json") if context else {},
		}
		return ToolExecutionResult(
			ok=False,
			capability_name=proposal.capability_name,
			status=status,
			reason=reason,
			failed_entities=[proposal.capability_name],
			verification=VerificationResult.not_checked(
				{
					"phase": "phase_2_runtime_separation",
					"note": "Rejected before domain execution.",
				}
			),
			raw_metadata=raw_metadata,
		)

	@staticmethod
	def _policy_result(
		proposal: ToolProposal,
		policy_decision: PolicyDecision,
		context: ExecutionContext | None,
		*,
		ok: bool,
		status: str,
	) -> ToolExecutionResult:
		entity = proposal.arguments.get("device_target") or proposal.capability_name
		verification = VerificationResult(
			status="noop" if policy_decision.decision == "noop" else "rejected",
			source="cached_state" if policy_decision.decision == "noop" else "policy",
			confidence=1.0,
			details={
				"policy_decision": policy_decision.model_dump(mode="json"),
			},
		)
		return ToolExecutionResult(
			ok=ok,
			capability_name=proposal.capability_name,
			status=status,
			reason=policy_decision.reason,
			unchanged_entities=[str(entity)] if ok else [],
			failed_entities=[proposal.capability_name] if not ok else [],
			verification=verification,
			policy_decision=policy_decision,
			raw_metadata={
				"proposal": proposal.model_dump(mode="json"),
				"policy_decision": policy_decision.model_dump(mode="json"),
				"runtime_context": context.model_dump(mode="json") if context else {},
				"user_visible_message": policy_decision.user_visible_message,
			},
		)
