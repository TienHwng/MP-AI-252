"""LangGraph-facing runtime tool execution node."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from schemas import ToolExecutionResult, ToolProposal

from runtime.execution_context import ExecutionContext
from runtime.tool_contracts import SUPPORTED_TOOL_NAMES
from runtime.tool_runner import ToolRunner


@dataclass(slots=True)
class RuntimeToolNodeResult:
	"""Structured output from executing model/planner tool proposals."""

	execution_results: list[ToolExecutionResult] = field(default_factory=list)


class RuntimeToolNode:
	"""Small graph node adapter around HERA's domain-safe ToolRunner."""

	def __init__(self, tool_runner: ToolRunner) -> None:
		self.tool_runner = tool_runner

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
		proposals = [
			self._proposal_from_tool_call(tool_call) for tool_call in tool_calls
		]
		return self.invoke(
			[proposal for proposal in proposals if proposal is not None],
			context,
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
		if name not in {"turn_on_device", "turn_off_device", "get_device_status"}:
			return None
		confidence = tool_call.get("confidence")
		if not isinstance(confidence, int | float):
			confidence = 0.6
		return ToolProposal(
			capability_name=name,
			arguments=args,
			rationale="Graph runtime converted native tool call into domain execution.",
			expected_outcome=(
				"Device state changes if requested state differs from current state."
				if name != "get_device_status"
				else "Current device state is reported without changing hardware."
			),
			confidence=max(0.0, min(float(confidence), 1.0)),
		)
