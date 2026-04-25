"""LangGraph topology for the HERA request pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orchestration.state import OrchestrationState

if TYPE_CHECKING:
	from agents.orchestrator import Orchestrator
	from core.message import UserMessage


class OrchestrationGraph:
	"""Compiled LangGraph pipeline for one HERA orchestrator instance."""

	def __init__(self, orchestrator: Orchestrator) -> None:
		self.orchestrator = orchestrator
		self.graph = self._compile_graph()

	async def run(self, message: UserMessage) -> OrchestrationState:
		return await self.graph.ainvoke({"message": message})

	def _compile_graph(self) -> Any:
		try:
			from langgraph.graph import END, StateGraph
		except ImportError as exc:
			raise RuntimeError(
				"LangGraph is required for Phase 5 orchestration. "
				"Install dependencies with: .venv\\Scripts\\pip.exe install -r requirements.txt"
			) from exc

		graph = StateGraph(OrchestrationState)
		graph.add_node("intake", self.orchestrator.graph_intake)
		graph.add_node("retrieve_memory", self.orchestrator.graph_retrieve_memory)
		graph.add_node("route", self.orchestrator.graph_route)
		graph.add_node("general", self.orchestrator.graph_general)
		graph.add_node("specialist", self.orchestrator.graph_specialist)
		graph.add_node("execute_tools", self.orchestrator.graph_execute_tools)
		graph.add_node("compose_response", self.orchestrator.graph_compose_response)
		graph.add_node("finalize", self.orchestrator.graph_finalize)

		graph.set_entry_point("intake")
		graph.add_edge("intake", "route")
		graph.add_edge("route", "retrieve_memory")
		graph.add_conditional_edges(
			"retrieve_memory",
			self._route_after_memory,
			{
				"general": "general",
				"specialist": "specialist",
			},
		)
		graph.add_edge("general", "finalize")
		graph.add_conditional_edges(
			"specialist",
			self._route_after_specialist,
			{
				"execute_tools": "execute_tools",
				"compose_response": "compose_response",
			},
		)
		graph.add_edge("execute_tools", "compose_response")
		graph.add_edge("compose_response", "finalize")
		graph.add_edge("finalize", END)
		return graph.compile()

	@staticmethod
	def _route_after_memory(state: OrchestrationState) -> str:
		route_decision = state["route_decision"]
		return "general" if route_decision.intent == "general" else "specialist"

	@staticmethod
	def _route_after_specialist(state: OrchestrationState) -> str:
		route_decision = state["route_decision"]
		return (
			"execute_tools" if route_decision.requires_execution else "compose_response"
		)
