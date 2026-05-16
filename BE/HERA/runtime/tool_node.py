"""LangGraph-facing runtime tool execution node."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from schemas import ToolExecutionResult, ToolProposal, VerificationResult

from runtime.execution_context import ExecutionContext
from runtime.read_tool_runner import ReadToolRunner
from runtime.tool_contracts import SUPPORTED_TOOL_NAMES
from runtime.tool_runner import ToolRunner


@dataclass(slots=True)
class RuntimeToolNodeResult:
	"""Structured output from executing model/planner tool proposals."""

	execution_results: list[ToolExecutionResult] = field(default_factory=list)


class RuntimeToolNode:
	"""Small graph node adapter around HERA's domain-safe ToolRunner."""

	def __init__(
		self,
		tool_runner: ToolRunner,
		read_tool_runner: ReadToolRunner | None = None,
	) -> None:
		self.tool_runner = tool_runner
		self.read_tool_runner = read_tool_runner

	def invoke(
		self,
		proposals: list[ToolProposal],
		context: ExecutionContext,
	) -> RuntimeToolNodeResult:
		return RuntimeToolNodeResult(
			execution_results=[
				self.tool_runner.run(proposal, context) for proposal in proposals
			],
		)

	def invoke_tool_calls(
		self,
		tool_calls: list[dict[str, Any]],
		context: ExecutionContext,
	) -> RuntimeToolNodeResult:
		read_results: list[ToolExecutionResult] = []
		proposals: list[ToolProposal] = []
		for tool_call in tool_calls:
			read_result = self._read_result_from_tool_call(tool_call, context)
			if read_result is not None:
				read_results.append(read_result)
				continue
			proposal = self._proposal_from_tool_call(tool_call)
			if proposal is not None:
				proposals.append(proposal)
		write_result = self.invoke(proposals, context)
		return RuntimeToolNodeResult(
			execution_results=[*read_results, *write_result.execution_results],
		)

	def _read_result_from_tool_call(
		self,
		tool_call: dict[str, Any],
		context: ExecutionContext,
	) -> ToolExecutionResult | None:
		if self.read_tool_runner is None:
			return None
		name = tool_call.get("name")
		if name not in {
			"get_current_telemetry",
			"get_telemetry_window",
			"get_device_status",
		}:
			return None
		args = tool_call.get("args", {})
		if not isinstance(args, dict):
			args = {}
		result = self.read_tool_runner.run(str(name), args)
		payload = result.get("result") if isinstance(result, dict) else {}
		if name == "get_device_status" and isinstance(payload, dict):
			raw_after_state = payload.get("device_status", {})
			after_state = raw_after_state if isinstance(raw_after_state, dict) else {}
		else:
			after_state = payload if isinstance(payload, dict) else {"value": payload}
		reason = str(
			result.get("reason") or ("read_ok" if result.get("ok") else "read_failed")
		)
		return ToolExecutionResult(
			ok=bool(result.get("ok")),
			capability_name=str(name),
			status=reason,
			reason=reason,
			after_state=after_state,
			verification=VerificationResult.not_checked(
				{
					"phase": "read_tool_runner",
					"note": "Read-only runtime tool executed without policy or side effects.",
				}
			),
			raw_metadata={
				"read_result": result,
				"target": payload.get("target") if isinstance(payload, dict) else None,
				"runtime_context": context.model_dump(mode="json"),
			},
		)

	@staticmethod
	def _proposal_from_tool_call(tool_call: dict[str, Any]) -> ToolProposal | None:
		name = tool_call.get("name")
		args = tool_call.get("args", {})
		if not isinstance(args, dict):
			args = {}
		if name not in SUPPORTED_TOOL_NAMES and name not in {
			"turn_on_device",
			"turn_off_device",
		}:
			return None
		if name == "set_device_state":
			# Compatibility input only; normalize to canonical write capabilities.
			state = args.get("state")
			if state is True:
				name = "turn_on_device"
			elif state is False:
				name = "turn_off_device"
			else:
				return None
			args = {"device_target": args.get("device_target")}
		if name in {
			"get_current_telemetry",
			"get_telemetry_window",
			"search_web",
			"fetch_web_page",
			"retrieve_memory",
			"store_memory",
		}:
			return None
		if name not in {
			"turn_on_device",
			"turn_off_device",
			"get_device_status",
			"set_device_value",
			"set_sensor_value",
		}:
			return None
		confidence = tool_call.get("confidence")
		if not isinstance(confidence, int | float):
			confidence = 0.6
		return ToolProposal(
			capability_name=name,
			arguments=args,
			rationale="Graph runtime converted native tool call into domain execution.",
			expected_outcome=(
				"Requested value changes if it differs from current telemetry."
				if name in {"set_device_value", "set_sensor_value"}
				else
				"Device state changes if requested state differs from current state."
				if name != "get_device_status"
				else "Current device state is reported without changing hardware."
			),
			confidence=max(0.0, min(float(confidence), 1.0)),
		)
