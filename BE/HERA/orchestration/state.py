"""State contract carried through the HERA LangGraph pipeline."""

from __future__ import annotations

from typing import Any, TypedDict

from core.message import AgentResponse, UserMessage
from schemas import IncomingRequest, MemoryContext, RouteDecision


class OrchestrationState(TypedDict, total=False):
	"""Mutable graph state for one user request."""

	message: UserMessage
	request: IncomingRequest
	memory_context: MemoryContext
	intent: str
	route_decision: RouteDecision
	specialist_response: AgentResponse
	response: AgentResponse
	start_time: float
	metadata: dict[str, Any]
