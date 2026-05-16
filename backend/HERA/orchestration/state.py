"""State contract carried through the HERA LangGraph pipeline."""

from __future__ import annotations

from typing import Any, TypedDict

from core.message import AgentResponse, UserMessage
from schemas import IncomingRequest, MemoryContext, RouteDecision


class OrchestrationState(TypedDict, total=False):
	"""Mutable graph state for one user request."""

	message: UserMessage
	request: IncomingRequest
	memory_context: MemoryContext | None
	intent: str
	route_decision: RouteDecision | None
	specialist_response: AgentResponse | None
	response: AgentResponse | None
	chat_history: list[dict[str, Any]]
	active_focus: dict[str, Any] | None
	pending_confirmation: dict[str, Any] | None
	pending_device_clarification: dict[str, Any] | None
	last_tool_results: list[dict[str, Any]]
	start_time: float
	metadata: dict[str, Any]
