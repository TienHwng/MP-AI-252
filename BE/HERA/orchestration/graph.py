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
		self.checkpointer = self._build_checkpointer()
		self.graph = self._compile_graph()

	async def run(self, message: UserMessage) -> OrchestrationState:
		config = {"configurable": {"thread_id": str(message.chat_id)}}
		return await self.graph.ainvoke({"message": message}, config=config)

	def clear_thread(self, thread_id: str) -> None:
		if hasattr(self.checkpointer, "delete_thread"):
			self.checkpointer.delete_thread(str(thread_id))

	def get_thread_state(self, thread_id: str) -> dict:
		config = {"configurable": {"thread_id": str(thread_id)}}
		snapshot = self.graph.get_state(config)
		return dict(getattr(snapshot, "values", {}) or {})

	def update_thread_state(self, thread_id: str, values: dict) -> None:
		config = {"configurable": {"thread_id": str(thread_id)}}
		self.graph.update_state(config, values)

	@staticmethod
	def _build_checkpointer() -> Any:
		try:
			from langgraph.checkpoint.memory import InMemorySaver
		except ImportError as exc:
			raise RuntimeError(
				"LangGraph checkpoint support is required for conversation state. "
				"Install dependencies with: .venv\\Scripts\\pip.exe install -r requirements.txt"
			) from exc
		return InMemorySaver()

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
		graph.add_node(
			"handle_pending_confirmation",
			self.orchestrator.graph_handle_pending_confirmation,
		)
		graph.add_node("general", self.orchestrator.graph_general)
		graph.add_node("specialist", self.orchestrator.graph_specialist)
		graph.add_node("ground_tool_plan", self.orchestrator.graph_ground_tool_plan)
		graph.add_node("execute_tools", self.orchestrator.graph_execute_tools)
		graph.add_node(
			"evaluate_tool_results",
			self.orchestrator.graph_evaluate_tool_results,
		)
		graph.add_node("compose_response", self.orchestrator.graph_compose_response)
		graph.add_node("finalize", self.orchestrator.graph_finalize)

		graph.set_entry_point("intake")
		graph.add_edge("intake", "route")
		graph.add_conditional_edges(
			"route",
			self._route_after_route,
			{
				"handle_pending_confirmation": "handle_pending_confirmation",
				"retrieve_memory": "retrieve_memory",
			},
		)
		graph.add_conditional_edges(
			"handle_pending_confirmation",
			self._route_after_confirmation,
			{
				"execute_tools": "execute_tools",
				"finalize": "finalize",
			},
		)
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
				"execute_tools": "ground_tool_plan",
				"compose_response": "compose_response",
			},
		)
		graph.add_edge("ground_tool_plan", "execute_tools")
		graph.add_edge("execute_tools", "evaluate_tool_results")
		graph.add_edge("evaluate_tool_results", "compose_response")
		graph.add_edge("compose_response", "finalize")
		graph.add_edge("finalize", END)
		return graph.compile(checkpointer=self.checkpointer)

	@staticmethod
	def _route_after_route(state: OrchestrationState) -> str:
		metadata = state.get("metadata", {})
		route_plan = (
			metadata.get("route_plan", {}) if isinstance(metadata, dict) else {}
		)
		if (
			isinstance(route_plan, dict)
			and route_plan.get("pending_mode") == "confirmation"
		):
			return "handle_pending_confirmation"
		return "retrieve_memory"

	@staticmethod
	def _route_after_confirmation(state: OrchestrationState) -> str:
		return "finalize" if state.get("response") is not None else "execute_tools"

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
