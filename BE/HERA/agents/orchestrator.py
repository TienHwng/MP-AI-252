"""
Orchestrator Agent (Router / Mediator)
=======================================
Receives every user message, classifies intent, and delegates
to the appropriate specialist agent.

Uses the configured orchestrator model for intent routing and general
conversation, then forwards specialist requests to the relevant agent.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime

from config import (
	FINAL_RESPONSE_TIMEOUT_SECONDS,
	GENERAL_RESPONSE_TIMEOUT_SECONDS,
	MAX_HISTORY,
	MAX_TOOL_ITERATIONS,
)
from core.llm_service import LLMService
from core.logger import (
	log_compose,
	log_exec,
	log_graph,
	log_memory,
	log_orch,
	log_route,
	log_runtime,
	trace_scope,
)
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService
from core.runtime_settings import runtime_settings
from memory import MemoryService
from orchestration import OrchestrationGraph, OrchestrationState
from prompts import (
	DEVICE_CONTROL_RESPONSE_SYSTEM,
	FINAL_RESPONSE_SYSTEM,
	GENERAL_SYSTEM,
	PENDING_CONFIRMATION_SYSTEM,
	ROUTER_SYSTEM,
)
from runtime import ExecutionContext, ToolRunner
from schemas import IncomingRequest, MemoryContext, RouteDecision, ToolProposal

from agents.base import AgentBase
from agents.device_agent import (
	looks_like_standalone_device_request,
	needs_recent_action_memory,
)
from agents.orchestrator_helpers import (
	clean_user_visible_text,
	fast_general_response,
	format_timestamp,
	looks_vietnamese,
	render_anomaly_text,
	render_device_control_text,
	render_device_specialist_fallback_text,
	render_sensor_text,
)

# ── Intent taxonomy ───────────────────────────────────────────

INTENTS = (
	"device_control",  # turn on/off LED, actuator commands
	"sensor_query",  # what is the temperature / humidity / status
	"anomaly_query",  # is there an anomaly, why is the score high
	"web_search",  # external/current public web information
	"general",  # greetings, help, chitchat, FAQ
)

MEMORY_SCOPES = {"none", "session", "actions", "profile", "all"}


class Orchestrator:
	"""
	Central mediator - not itself an ``AgentBase`` because it *delegates*
	rather than generating a final user-facing response.
	"""

	def __init__(
		self,
		llm: LLMService,
		agents: dict[str, AgentBase],
		mqtt: MQTTService,
		*,
		tool_runner: ToolRunner | None = None,
		memory_service: MemoryService | None = None,
		orchestrator_model: str | None = None,
	) -> None:
		self.llm = llm
		self.agents = agents
		self.mqtt = mqtt
		self.tool_runner = tool_runner
		self.memory_service = memory_service
		self.orchestrator_model = orchestrator_model
		# per-chat conversation history for general conversation
		self.conversations: dict[str, list[dict]] = {}
		self.pending_confirmations: dict[str, dict] = {}
		self.pending_device_clarifications: dict[str, dict] = {}
		self.graph = OrchestrationGraph(self)

	# ── public entry point ────────────────────────────────────

	async def handle(self, message: UserMessage) -> AgentResponse:
		"""Run one request through the LangGraph orchestration pipeline."""
		with trace_scope(chat_id=message.chat_id):
			log_graph(
				"Pipeline start",
				detail=f"user: {message.text[:80]}{'…' if len(message.text) > 80 else ''}",
			)
			state = await self.graph.run(message)
			return state["response"]

	def graph_intake(self, state: OrchestrationState) -> OrchestrationState:
		message = state["message"]
		request = IncomingRequest.from_user_message(message)
		chat_id = message.chat_id
		if chat_id not in self.conversations:
			self.conversations[chat_id] = []
		log_graph(
			"Intake",
			data={
				"req": request.request_id[:8],
				"session": request.session_id[:12],
				"user": request.user_id,
				"history_len": len(self.conversations[chat_id]),
			},
		)
		return {
			"request": request,
			"start_time": time.perf_counter(),
			"metadata": {},
		}

	def _get_chat_history(self, chat_id: str) -> list[dict]:
		"""Return the recent conversation history for a chat."""
		return self.conversations.get(chat_id, [])

	def graph_retrieve_memory(self, state: OrchestrationState) -> OrchestrationState:
		request = state["request"]
		route_plan = state.get("metadata", {}).get("route_plan", {})
		if not isinstance(route_plan, dict):
			route_plan = {}
		memory_scope = str(route_plan.get("memory_scope") or "none")
		if memory_scope == "none":
			log_memory("Skipped (memory_scope=none)")
			return {
				"memory_context": MemoryContext(
					available=self.memory_available(),
					reason="memory_scope_none",
				)
			}
		memory_ctx = self.retrieve_memory(request, memory_scope=memory_scope)
		log_memory(
			"Retrieved",
			data={
				"available": memory_ctx.available,
				"reason": memory_ctx.reason or "ok",
				"scope": memory_scope,
			},
		)
		return {"memory_context": memory_ctx}

	async def graph_route(self, state: OrchestrationState) -> OrchestrationState:
		message = state["message"]
		request = state["request"]
		metadata = state.get("metadata", {})
		pending = self.pending_confirmations.get(request.session_id)
		if pending is not None:
			confirmation_decision = await self.classify_pending_confirmation(
				message.text,
			)
			metadata["pending_confirmation"] = {
				"decision": confirmation_decision,
				"pending_request_id": pending.get("request_id"),
				"pending_reason": pending.get("reason"),
			}
			if confirmation_decision in {"confirm", "cancel", "unclear"}:
				return {
					"intent": "device_control",
					"route_decision": RouteDecision.from_intent(
						"device_control",
						max_tool_steps=MAX_TOOL_ITERATIONS,
					),
					"metadata": {
						**metadata,
						"route_plan": {
							"intent": "device_control",
							"memory_scope": "none",
							"direct_response": None,
							"pending_mode": "confirmation",
							"confidence": 1.0,
						},
					},
				}
			if confirmation_decision == "new_request":
				self.pending_confirmations.pop(request.session_id, None)

		pending_clarification = self.pending_device_clarifications.get(
			request.session_id
		)
		route_plan = await self.classify_route(
			message.text,
			chat_id=message.chat_id,
			pending_device_clarification=pending_clarification,
		)
		if pending_clarification is not None:
			if route_plan.get("pending_mode") == "clarification_answer":
				pending_action = pending_clarification.get("requested_action")
				resolution = await self.resolve_pending_device_target(
					message,
					requested_action=str(pending_action),
				)
				resolved_target = resolution.get("target")
				if (
					pending_action in {"turn_on", "turn_off", "status"}
					and resolved_target
				):
					metadata["pending_device_clarification"] = {
						"requested_action": pending_action,
						"resolved_target": resolved_target,
						"confidence": resolution.get("confidence"),
						"pending_request_id": pending_clarification.get("request_id"),
					}
					self.pending_device_clarifications.pop(request.session_id, None)
					route_plan = {
						**route_plan,
						"intent": "device_control",
						"memory_scope": "none",
					}
				else:
					route_plan = {
						**route_plan,
						"intent": "device_control",
						"memory_scope": "none",
					}
					metadata["pending_device_clarification"] = {
						"requested_action": pending_action,
						"resolved_target": None,
						"confidence": resolution.get("confidence"),
						"pending_request_id": pending_clarification.get("request_id"),
						"clarification_question": pending_clarification.get(
							"clarification_question"
						),
						"unresolved": True,
					}
			else:
				self.pending_device_clarifications.pop(request.session_id, None)

		intent = str(route_plan["intent"])
		route_decision = RouteDecision.from_intent(
			intent,
			max_tool_steps=MAX_TOOL_ITERATIONS,
		)
		log_route(
			f"Intent classified: {intent!r}",
			data={
				"specialist": route_decision.specialist,
				"requires_exec": route_decision.requires_execution,
				"risk": route_decision.risk_level,
			},
		)
		return {
			"intent": intent,
			"route_decision": route_decision,
			"metadata": {**metadata, "route_plan": route_plan},
		}

	async def graph_general(self, state: OrchestrationState) -> OrchestrationState:
		log_orch("Handling as general conversation")
		route_plan = state.get("metadata", {}).get("route_plan", {})
		if isinstance(route_plan, dict):
			direct_response = route_plan.get("direct_response")
			if isinstance(direct_response, str) and direct_response.strip():
				return {
					"response": AgentResponse(
						text=clean_user_visible_text(direct_response),
						agent_name="orchestrator",
						metadata={"route_direct_response": True},
					)
				}
		return {
			"response": await self.handle_general(
				state["message"],
				state.get("memory_context"),
			)
		}

	async def graph_specialist(self, state: OrchestrationState) -> OrchestrationState:
		message = state["message"]
		request = state["request"]
		route_decision = state["route_decision"]
		memory_context = state["memory_context"]
		pending_metadata = state.get("metadata", {}).get("pending_confirmation", {})
		device_clarification = state.get("metadata", {}).get(
			"pending_device_clarification",
		)
		if isinstance(device_clarification, dict):
			requested_action = device_clarification.get("requested_action")
			resolved_target = device_clarification.get("resolved_target")
			if device_clarification.get("unresolved"):
				return {
					"specialist_response": self.build_unresolved_device_clarification_response(
						str(requested_action),
						route_decision.specialist,
						str(
							device_clarification.get("clarification_question")
							or "Bạn muốn mình điều khiển thiết bị nào?"
						),
					)
				}
			if requested_action in {"turn_on", "turn_off", "status"} and isinstance(
				resolved_target, str
			):
				return {
					"specialist_response": self.build_device_clarification_response(
						requested_action,
						resolved_target,
						route_decision.specialist,
						confidence=float(device_clarification.get("confidence") or 0.9),
					)
				}
		if isinstance(pending_metadata, dict):
			pending_decision = pending_metadata.get("decision")
			if pending_decision in {"confirm", "cancel", "unclear"}:
				return await self.handle_pending_confirmation(
					message,
					request,
					route_decision,
					str(pending_decision),
				)

		agent_key = route_decision.specialist
		agent = self.agents.get(agent_key)

		if agent is None:
			log_orch(
				f"No specialist for intent={route_decision.intent!r}, fallback to general",
			)
			return {"response": await self.handle_general(message)}

		log_orch(
			f"Delegating to specialist: {agent.name}",
			data={
				"intent": route_decision.intent,
				"risk": route_decision.risk_level,
			},
		)
		specialist_response = await agent.process(
			message,
			{
				"history": self.conversations[message.chat_id],
				"incoming_request": request,
				"route_decision": route_decision,
				"route_plan": state.get("metadata", {}).get("route_plan", {}),
				"memory_context": memory_context.model_dump(mode="json"),
				"sensor_snapshot": self.mqtt.get_sensor_snapshot(),
			},
		)
		self.maybe_store_pending_device_clarification(request, specialist_response)
		return {"specialist_response": specialist_response}

	def graph_execute_tools(self, state: OrchestrationState) -> OrchestrationState:
		if "specialist_response" not in state:
			return {}
		route_decision = state.get("route_decision")
		if (
			isinstance(route_decision, RouteDecision)
			and not route_decision.requires_execution
		):
			log_runtime("Skipped (no execution required)")
			return {}
		log_runtime("Executing tool proposals...")
		return {
			"specialist_response": self.run_tool_runtime(
				state["specialist_response"],
				state["request"],
				state["route_decision"],
			)
		}

	async def graph_compose_response(
		self, state: OrchestrationState
	) -> OrchestrationState:
		if "response" in state:
			return {}
		log_compose("Composing final user-facing response...")
		return {
			"response": await self.compose_final_response(
				state["message"],
				state["route_decision"],
				state["specialist_response"],
			)
		}

	def graph_finalize(self, state: OrchestrationState) -> OrchestrationState:
		message = state["message"]
		request = state["request"]
		route_decision = state["route_decision"]
		memory_context = state["memory_context"]
		response = state["response"]
		chat_id = message.chat_id

		if response.tools_used:
			# Keep minimal context so next message can reference what just happened
			self.conversations[chat_id] = [
				{"role": "user", "content": message.text},
				{"role": "assistant", "content": response.text},
			]
		else:
			self.conversations[chat_id].append(
				{"role": "user", "content": message.text},
			)
			self.conversations[chat_id].append(
				{"role": "assistant", "content": response.text},
			)
			if len(self.conversations[chat_id]) > MAX_HISTORY:
				self.conversations[chat_id] = self.conversations[chat_id][-MAX_HISTORY:]

		elapsed = time.perf_counter() - state["start_time"]
		response.metadata["latency_s"] = round(elapsed, 2)
		response.metadata["intent"] = route_decision.intent
		response.metadata["request"] = request.model_dump(mode="json")
		response.metadata["route_decision"] = route_decision.model_dump(mode="json")
		response.metadata["memory_context"] = memory_context.model_dump(mode="json")
		response.metadata["memory_write"] = self.record_memory_turn(
			request,
			response,
			route_decision.intent,
		)
		tools_str = ", ".join(response.tools_used) if response.tools_used else "none"
		log_graph(
			f"Pipeline done in {elapsed:.2f}s",
			data={
				"intent": route_decision.intent,
				"agent": response.agent_name,
				"tools": tools_str,
			},
			detail=f"Reply: {response.text[:100]}{'…' if len(response.text) > 100 else ''}",
		)

		return {"response": response}

	def retrieve_memory(
		self,
		request: IncomingRequest,
		*,
		memory_scope: str = "all",
	) -> MemoryContext:
		if self.memory_service is None:
			return MemoryContext(
				available=False, reason="memory_service_not_configured"
			)
		scopes = self.memory_scope_to_store_scopes(memory_scope)
		if hasattr(self.memory_service, "retrieve_scoped"):
			return self.memory_service.retrieve_scoped(request, scopes)
		return self.memory_service.retrieve(request)

	@staticmethod
	def memory_scope_to_store_scopes(memory_scope: str) -> set[str]:
		if memory_scope == "session":
			return {"session"}
		if memory_scope == "actions":
			return {"actions"}
		if memory_scope == "profile":
			return {"profile"}
		if memory_scope == "all":
			return {"session", "actions", "profile"}
		return set()

	def memory_available(self) -> bool:
		if self.memory_service is None:
			return False
		mongo = getattr(self.memory_service, "mongo", None)
		return bool(getattr(mongo, "available", False))

	def record_memory_turn(
		self,
		request: IncomingRequest,
		response: AgentResponse,
		intent: str,
	) -> dict:
		if self.memory_service is None:
			return {"status": "skipped", "reason": "memory_service_not_configured"}
		ok = self.memory_service.record_turn(request, response, intent=intent)
		return {"status": "written" if ok else "skipped"}

	def reset_history(self, chat_id: str) -> None:
		self.conversations.pop(chat_id, None)

	@staticmethod
	def _format_timestamp(value: str | None) -> str | None:
		return format_timestamp(value)

	@staticmethod
	def _looks_vietnamese(text: str) -> bool:
		return looks_vietnamese(text)

	@staticmethod
	def _format_entity_list(items: list[str], prefer_vietnamese: bool) -> str:
		if not items:
			return ""
		if len(items) == 1:
			return items[0]
		if len(items) == 2:
			joiner = " và " if prefer_vietnamese else " and "
			return f"{items[0]}{joiner}{items[1]}"
		last_joiner = ", và " if prefer_vietnamese else ", and "
		return ", ".join(items[:-1]) + last_joiner + items[-1]

	@staticmethod
	def _action_label(capability_name: str, prefer_vietnamese: bool) -> str:
		labels = {
			"turn_on_device": ("bật", "turn on"),
			"turn_off_device": ("tắt", "turn off"),
			"get_device_status": ("kiểm tra trạng thái", "check the status of"),
		}
		vi, en = labels.get(capability_name, ("điều khiển", "control"))
		return vi if prefer_vietnamese else en

	@staticmethod
	def _requested_action_text(action: str, prefer_vietnamese: bool) -> str:
		labels = {
			"turn_on": ("bật", "turn something on"),
			"turn_off": ("tắt", "turn something off"),
			"status": ("kiểm tra trạng thái", "check the status"),
		}
		vi, en = labels.get(action, ("điều khiển", "control something"))
		return vi if prefer_vietnamese else en

	def render_device_control_text(self, user_text: str, payload: dict) -> str:
		return render_device_control_text(user_text, payload)

	def render_device_specialist_fallback_text(
		self,
		user_text: str,
		specialist_response: AgentResponse,
	) -> str:
		return render_device_specialist_fallback_text(user_text, specialist_response)

	def render_sensor_text(
		self, user_text: str, specialist_response: AgentResponse
	) -> str:
		return render_sensor_text(user_text, specialist_response)

	def render_anomaly_text(
		self, user_text: str, specialist_response: AgentResponse
	) -> str:
		return render_anomaly_text(user_text, specialist_response)

	def render_web_research_text(
		self, user_text: str, specialist_response: AgentResponse
	) -> str:
		prefer_vietnamese = looks_vietnamese(user_text)
		raw_report = specialist_response.metadata.get("specialist_report")
		report = raw_report if isinstance(raw_report, dict) else {}
		analysis_payload = report.get("analysis_payload", {})
		if not isinstance(analysis_payload, dict):
			analysis_payload = specialist_response.metadata.get("web_research", {})
		if not isinstance(analysis_payload, dict):
			analysis_payload = {}

		mode = analysis_payload.get("mode")
		if mode == "fetch":
			fetch = analysis_payload.get("fetch", {})
			if isinstance(fetch, dict) and fetch.get("status") == "ok":
				title = str(fetch.get("title") or "trang này").strip()
				url = str(fetch.get("url") or "").strip()
				content = self._short_plain_snippet(fetch.get("content"))
				if prefer_vietnamese:
					return f"Mình đọc được {title}: {content} Nguồn: {url}".strip()
				return f"I found this on {title}: {content} Source: {url}".strip()
			reason = fetch.get("reason") if isinstance(fetch, dict) else "unknown"
			return self.web_unavailable_text(str(reason), prefer_vietnamese)

		search = analysis_payload.get("search", {})
		if isinstance(search, dict) and search.get("status") == "ok":
			results = search.get("results", [])
			if not isinstance(results, list) or not results:
				return (
					"Mình đã tìm nhưng chưa thấy kết quả phù hợp."
					if prefer_vietnamese
					else "I searched but did not find a useful result."
				)
			top = results[0] if isinstance(results[0], dict) else {}
			title = str(top.get("title") or "kết quả đầu tiên").strip()
			url = str(top.get("url") or "").strip()
			content = self._short_plain_snippet(top.get("content"))
			if prefer_vietnamese:
				return f"Mình tìm thấy {title}: {content} Nguồn: {url}".strip()
			return f"I found {title}: {content} Source: {url}".strip()
		reason = search.get("reason") if isinstance(search, dict) else "unknown"
		return self.web_unavailable_text(str(reason), prefer_vietnamese)

	@staticmethod
	def _short_plain_snippet(value: object, max_chars: int = 420) -> str:
		text = " ".join(str(value or "").split())
		if len(text) <= max_chars:
			return text
		return text[: max_chars - 1].rstrip() + "…"

	@staticmethod
	def web_unavailable_text(reason: str, prefer_vietnamese: bool) -> str:
		if reason == "web_search_disabled":
			return (
				"Web search đang bị tắt trong cấu hình."
				if prefer_vietnamese
				else "Web search is disabled in the current configuration."
			)
		return (
			"Mình chưa lấy được kết quả web lúc này."
			if prefer_vietnamese
			else "I could not retrieve web results right now."
		)

	def fast_general_response(self, user_text: str) -> str | None:
		return fast_general_response(user_text)

	def maybe_store_pending_device_clarification(
		self,
		request: IncomingRequest,
		specialist_response: AgentResponse,
	) -> None:
		raw_report = specialist_response.metadata.get("specialist_report")
		if not isinstance(raw_report, dict):
			return
		question = raw_report.get("clarification_question")
		payload = raw_report.get("analysis_payload", {})
		if not question or not isinstance(payload, dict):
			return
		parsed_command = payload.get("parsed_command", {})
		if not isinstance(parsed_command, dict):
			return
		requested_action = parsed_command.get("requested_action")
		if requested_action not in {"turn_on", "turn_off", "status"}:
			return
		self.pending_device_clarifications[request.session_id] = {
			"request_id": request.request_id,
			"requested_action": requested_action,
			"clarification_question": question,
			"created_at": time.time(),
		}

	async def resolve_pending_device_target(
		self,
		message: UserMessage,
		*,
		requested_action: str,
	) -> dict:
		agent = self.agents.get("device_control")
		resolver = getattr(agent, "resolve_target_from_clarification", None)
		if callable(resolver):
			return await resolver(message, requested_action=requested_action)
		return {"target": None, "confidence": 0.0}

	def build_device_clarification_response(
		self,
		requested_action: str,
		resolved_target: str,
		agent_name: str,
		confidence: float = 0.9,
	) -> AgentResponse:
		capability_name = {
			"turn_on": "turn_on_device",
			"turn_off": "turn_off_device",
			"status": "get_device_status",
		}[requested_action]
		proposal = ToolProposal(
			capability_name=capability_name,
			arguments={"device_target": resolved_target},
			rationale="Resolved device target from the user's clarification reply.",
			expected_outcome=(
				"Device state changes if requested state differs from current state."
				if capability_name != "get_device_status"
				else "Current device state is reported without changing hardware."
			),
			confidence=confidence,
		)
		report = {
			"parsed_command": {
				"action": requested_action,
				"target": resolved_target,
				"reference": "none",
				"confidence": confidence,
				"requested_action": requested_action,
				"requested_target": resolved_target,
			},
			"tool_proposals": [proposal.model_dump(mode="json")],
			"device_status": self.tool_runner.get_device_status_report()
			if self.tool_runner
			else {},
		}
		analysis_payload = dict(report)
		specialist_report = {
			"specialist_name": agent_name,
			"summary": "tool_proposal_ready",
			"tool_proposals": [proposal.model_dump(mode="json")],
			"clarification_question": None,
			"analysis_payload": analysis_payload,
		}
		report["specialist_report"] = specialist_report
		return AgentResponse(
			text=json.dumps(report, ensure_ascii=False),
			agent_name=agent_name,
			metadata=report,
		)

	def build_unresolved_device_clarification_response(
		self,
		requested_action: str,
		agent_name: str,
		clarification_question: str,
	) -> AgentResponse:
		report = {
			"parsed_command": {
				"action": requested_action,
				"target": None,
				"reference": "none",
				"confidence": 0.0,
				"requested_action": requested_action,
				"requested_target": None,
			},
			"tool_proposals": [],
			"device_status": self.tool_runner.get_device_status_report()
			if self.tool_runner
			else {},
		}
		analysis_payload = dict(report)
		specialist_report = {
			"specialist_name": agent_name,
			"summary": "awaiting_target_clarification",
			"tool_proposals": [],
			"clarification_question": clarification_question,
			"analysis_payload": analysis_payload,
		}
		report["specialist_report"] = specialist_report
		return AgentResponse(
			text=json.dumps(report, ensure_ascii=False),
			agent_name=agent_name,
			metadata=report,
		)

	def run_tool_runtime(
		self,
		specialist_response: AgentResponse,
		request: IncomingRequest,
		route_decision: RouteDecision,
	) -> AgentResponse:
		"""Run specialist proposals through the central runtime boundary."""
		if self.tool_runner is None:
			specialist_response.metadata["tool_runtime"] = {
				"status": "skipped",
				"reason": "tool_runner_not_configured",
			}
			return specialist_response

		proposals = self.extract_tool_proposals(specialist_response)
		if not proposals:
			log_runtime("No tool proposals from specialist")
			specialist_response.metadata["tool_runtime"] = {
				"status": "skipped",
				"reason": "no_tool_proposals",
			}
			return specialist_response

		context = ExecutionContext(
			request_id=request.request_id,
			session_id=request.session_id,
			user_id=request.user_id,
			channel=request.channel,
			route_intent=route_decision.intent,
			specialist=route_decision.specialist,
			metadata={
				"risk_level": route_decision.risk_level,
				"capability_scope": route_decision.capability_scope,
			},
		)
		log_runtime(
			f"Running {len(proposals)} proposal(s)",
			data={
				"capabilities": [p.capability_name for p in proposals],
				"risk": route_decision.risk_level,
			},
		)
		execution_results = self.tool_runner.run_all(proposals, context)
		for r in execution_results:
			log_exec(
				f"{r.capability_name}: {r.status}",
				data={
					"ok": r.ok,
					"reason": r.reason or "success",
					"changed": r.changed_entities or [],
					"verify": r.verification.status if r.verification else "?",
				},
			)
		for proposal, result in zip(proposals, execution_results, strict=False):
			self.maybe_store_pending_confirmation(request, proposal, result)
		action_summaries = []
		if self.memory_service is not None:
			action_summaries = self.memory_service.record_tool_results(
				request,
				context,
				execution_results,
				original_text=request.text,
			)
		execution_payloads = [
			result.model_dump(mode="json") for result in execution_results
		]
		specialist_response.metadata["tool_runtime"] = {
			"status": "completed",
			"execution_context": context.model_dump(mode="json"),
			"execution_results": execution_payloads,
			"memory_action_summaries": [
				summary.model_dump(mode="json") for summary in action_summaries
			],
		}
		specialist_response.metadata["tool_execution_results"] = execution_payloads
		if execution_results:
			first_result = execution_results[0]
			specialist_response.metadata["execution_result"] = first_result.raw_metadata
			specialist_response.metadata["tool_execution_result"] = (
				first_result.model_dump(mode="json")
			)
		specialist_response.tools_used = [
			result.capability_name for result in execution_results if result.ok
		]
		specialist_response.text = json.dumps(
			specialist_response.metadata,
			ensure_ascii=False,
		)
		return specialist_response

	@staticmethod
	def extract_tool_proposals(response: AgentResponse) -> list[ToolProposal]:
		raw_report = response.metadata.get("specialist_report")
		raw_proposals = []
		if isinstance(raw_report, dict):
			raw_proposals = raw_report.get("tool_proposals", [])
		if not raw_proposals:
			raw_proposals = response.metadata.get("tool_proposals", [])

		proposals: list[ToolProposal] = []
		for raw_proposal in raw_proposals:
			if isinstance(raw_proposal, ToolProposal):
				proposals.append(raw_proposal)
			elif isinstance(raw_proposal, dict):
				proposals.append(ToolProposal.model_validate(raw_proposal))
		return proposals

	async def handle_pending_confirmation(
		self,
		message: UserMessage,
		request: IncomingRequest,
		route_decision: RouteDecision,
		decision: str,
	) -> OrchestrationState:
		pending = self.pending_confirmations.get(request.session_id)
		if pending is None:
			return {}

		if decision == "cancel":
			self.pending_confirmations.pop(request.session_id, None)
			text = await self.compose_device_control_user_text(
				message.text,
				{
					"status": "pending_cancelled",
				},
			)
			return {
				"response": AgentResponse(
					text=text,
					agent_name="orchestrator",
					metadata={
						"pending_confirmation": {
							"decision": "cancel",
							"status": "cleared",
						}
					},
				)
			}

		if decision == "unclear":
			text = await self.compose_device_control_user_text(
				message.text,
				{
					"status": "pending_unclear",
					"pending": self.sanitise_pending_confirmation(pending),
				},
			)
			return {
				"response": AgentResponse(
					text=text,
					agent_name="orchestrator",
					metadata={
						"pending_confirmation": {
							"decision": "unclear",
							"status": "waiting",
						}
					},
				)
			}

		raw_proposal = pending.get("proposal", {})
		proposal = ToolProposal.model_validate(raw_proposal)
		confirmed_arguments = {**proposal.arguments, "_confirmed": True}
		confirmed_proposal = proposal.model_copy(
			update={"arguments": confirmed_arguments}
		)
		self.pending_confirmations.pop(request.session_id, None)

		report = {
			"pending_confirmation": {
				"decision": "confirm",
				"confirmed_request_id": pending.get("request_id"),
				"status": "confirmed",
			},
			"tool_proposals": [confirmed_proposal.model_dump(mode="json")],
		}
		return {
			"specialist_response": AgentResponse(
				text=json.dumps(report, ensure_ascii=False),
				agent_name=route_decision.specialist,
				metadata=report,
			)
		}

	def maybe_store_pending_confirmation(
		self,
		request: IncomingRequest,
		proposal: ToolProposal,
		result,
	) -> None:
		policy_decision = result.policy_decision
		if (
			result.status != "ask"
			or policy_decision is None
			or policy_decision.reason != "broad_all_devices_scope_requires_confirmation"
		):
			return
		self.pending_confirmations[request.session_id] = {
			"request_id": request.request_id,
			"user_id": request.user_id,
			"proposal": proposal.model_dump(mode="json"),
			"reason": policy_decision.reason,
			"user_visible_message": policy_decision.user_visible_message,
			"created_at": time.time(),
		}

	async def classify_pending_confirmation(self, text: str) -> str:
		normalized = " ".join(text.strip().lower().split())
		if any(
			token in normalized
			for token in (
				"xác nhận",
				"confirm",
				"dong y",
				"đồng ý",
				"ok",
				"okay",
				"yes",
			)
		) or normalized in {"ừ", "uh", "um", "ừm"}:
			return "confirm"
		if any(
			token in normalized
			for token in ("hủy", "huỷ", "cancel", "thôi", "bỏ đi", "không")
		):
			return "cancel"
		if looks_like_standalone_device_request(text):
			return "new_request"
		messages = [
			{"role": "system", "content": PENDING_CONFIRMATION_SYSTEM},
			{"role": "user", "content": text},
		]
		orchestrator_model = (
			self.orchestrator_model
			or runtime_settings.get_active_model(
				"orchestratorModel",
			)
		)
		result = await asyncio.to_thread(
			self.llm.completion,
			messages,
			None,
			orchestrator_model,
		)
		raw = (result["content"] or "").strip().lower()
		for label in ("confirm", "cancel", "new_request", "unclear"):
			if label in raw:
				return label
		return "unclear"

	# ── intent classification ─────────────────────────────────

	async def classify_route(
		self,
		text: str,
		*,
		chat_id: str | None = None,
		pending_device_clarification: dict | None = None,
	) -> dict:
		"""Return a structured route and memory policy."""
		if (
			pending_device_clarification is None
			and looks_like_standalone_device_request(text)
			and not needs_recent_action_memory(text)
		):
			log_route(
				"Fast route: 'device_control'",
				data={"method": "device_parser"},
			)
			return {
				"intent": "device_control",
				"memory_scope": "none",
				"direct_response": None,
				"pending_mode": "none",
				"confidence": 1.0,
			}

		history = self._get_chat_history(chat_id) if chat_id else []
		router_payload = {
			"current_message": text,
			"pending_device_clarification": pending_device_clarification,
		}
		messages = [
			{"role": "system", "content": ROUTER_SYSTEM},
			*history[-4:],
			{
				"role": "user",
				"content": json.dumps(router_payload, ensure_ascii=False),
			},
		]
		orchestrator_model = (
			self.orchestrator_model
			or runtime_settings.get_active_model(
				"orchestratorModel",
			)
		)
		result = await asyncio.to_thread(
			self.llm.completion,
			messages,
			None,
			orchestrator_model,
		)
		return self.normalise_route_plan(result.get("content"))

	async def classify_intent(self, text: str, *, chat_id: str | None = None) -> str:
		"""Compatibility wrapper for tests and callers needing only intent."""
		return str((await self.classify_route(text, chat_id=chat_id))["intent"])

	@staticmethod
	def normalise_route_plan(raw_text: str | None) -> dict:
		raw = (raw_text or "").strip()
		parsed: dict = {}
		if raw:
			start = raw.find("{")
			end = raw.rfind("}")
			if start != -1 and end > start:
				try:
					candidate = json.loads(raw[start : end + 1])
				except json.JSONDecodeError:
					candidate = {}
				if isinstance(candidate, dict):
					parsed = candidate
		intent = parsed.get("intent")
		if intent not in INTENTS:
			lower_raw = raw.lower()
			intent = next((item for item in INTENTS if item in lower_raw), "general")
		memory_scope = parsed.get("memory_scope")
		if memory_scope not in MEMORY_SCOPES:
			memory_scope = "none"
		direct_response = parsed.get("direct_response")
		if intent != "general" or memory_scope != "none":
			direct_response = None
		if not isinstance(direct_response, str):
			direct_response = None
		web_query = parsed.get("web_query")
		if (
			intent != "web_search"
			or not isinstance(web_query, str)
			or not web_query.strip()
		):
			web_query = None
		else:
			web_query = " ".join(web_query.split())
		pending_mode = parsed.get("pending_mode")
		if pending_mode not in {"none", "clarification_answer", "new_request"}:
			pending_mode = "none"
		confidence = parsed.get("confidence")
		if not isinstance(confidence, int | float):
			confidence = 0.0
		return {
			"intent": intent,
			"memory_scope": memory_scope,
			"direct_response": direct_response,
			"web_query": web_query,
			"pending_mode": pending_mode,
			"confidence": max(0.0, min(float(confidence), 1.0)),
		}

	async def handle_general(
		self,
		message: UserMessage,
		memory_context: MemoryContext | None = None,
	) -> AgentResponse:
		"""Use the orchestrator model directly for general conversation."""
		fast_response = self.fast_general_response(message.text)
		if fast_response is not None:
			return AgentResponse(
				text=clean_user_visible_text(fast_response),
				agent_name="orchestrator",
			)
		history = self.conversations.get(message.chat_id, [])
		sensor_context = json.dumps(self.mqtt.get_sensor_snapshot(), indent=2)
		memory_payload = (
			memory_context.model_dump(mode="json")
			if isinstance(memory_context, MemoryContext)
			else {}
		)
		memory_context_text = json.dumps(
			memory_payload,
			ensure_ascii=False,
			indent=2,
		)
		time_context = self.build_time_context()
		messages = [
			{
				"role": "system",
				"content": GENERAL_SYSTEM.format(
					sensor_context=sensor_context,
					time_context=time_context,
					memory_context=memory_context_text,
				),
			},
			*history[-MAX_HISTORY:],
			{"role": "user", "content": message.text},
		]
		orchestrator_model = (
			self.orchestrator_model
			or runtime_settings.get_active_model(
				"orchestratorModel",
			)
		)
		try:
			result = await asyncio.wait_for(
				asyncio.to_thread(
					self.llm.completion,
					messages,
					None,
					orchestrator_model,
				),
				timeout=GENERAL_RESPONSE_TIMEOUT_SECONDS,
			)
		except TimeoutError:
			return AgentResponse(
				text=self.general_timeout_fallback(message.text),
				agent_name="orchestrator",
				metadata={
					"fallback_reason": "general_llm_timeout",
					"timeout_s": GENERAL_RESPONSE_TIMEOUT_SECONDS,
				},
			)
		return AgentResponse(
			text=clean_user_visible_text(result["content"] or "(no response)"),
			agent_name="orchestrator",
		)

	@staticmethod
	def build_time_context() -> str:
		now = datetime.now().astimezone()
		weekday_vi = [
			"Thứ Hai",
			"Thứ Ba",
			"Thứ Tư",
			"Thứ Năm",
			"Thứ Sáu",
			"Thứ Bảy",
			"Chủ Nhật",
		][now.weekday()]
		return f"{weekday_vi}, {now:%d/%m/%Y %H:%M:%S} (UTC offset {now:%z})"

	@staticmethod
	def general_timeout_fallback(user_text: str) -> str:
		if looks_vietnamese(user_text):
			return (
				"Mình đang phản hồi hơi chậm. Bạn nhắn lại giúp mình một lần nữa nhé."
			)
		return "I am taking too long to respond. Please send that again."

	async def compose_final_response(
		self,
		message: UserMessage,
		route_decision: RouteDecision,
		specialist_response: AgentResponse,
	) -> AgentResponse:
		"""Convert a specialist report into the final user-facing reply."""
		if route_decision.intent == "device_control":
			device_response = await self.compose_device_control_response(
				message,
				specialist_response,
			)
			if device_response is not None:
				return device_response
		if route_decision.intent == "sensor_query":
			return await self.compose_natural_specialist_response(
				message,
				route_decision,
				specialist_response,
				system_prompt=FINAL_RESPONSE_SYSTEM,
				fallback_text=self.render_sensor_text(
					message.text, specialist_response
				),
			)
		if route_decision.intent == "anomaly_query":
			return await self.compose_natural_specialist_response(
				message,
				route_decision,
				specialist_response,
				system_prompt=FINAL_RESPONSE_SYSTEM,
				fallback_text=self.render_anomaly_text(
					message.text, specialist_response
				),
			)
		if route_decision.intent == "web_search":
			return await self.compose_natural_specialist_response(
				message,
				route_decision,
				specialist_response,
				system_prompt=FINAL_RESPONSE_SYSTEM,
				fallback_text=self.render_web_research_text(
					message.text, specialist_response
				),
			)

		payload = {
			"user_message": message.text,
			"route_decision": route_decision.model_dump(mode="json"),
			"specialist": self.sanitise_specialist_payload(specialist_response),
			"sensor_snapshot": self.mqtt.get_sensor_snapshot(),
		}
		final_text = await self.compose_text_with_llm(
			FINAL_RESPONSE_SYSTEM,
			payload,
			fallback_text=specialist_response.text,
		)
		return AgentResponse(
			text=final_text,
			agent_name="orchestrator",
			tools_used=list(specialist_response.tools_used),
			confidence=specialist_response.confidence,
			metadata={
				"specialist_agent": specialist_response.agent_name,
				"specialist_report": specialist_response.text,
				"specialist_metadata": specialist_response.metadata,
			},
		)

	async def compose_device_control_response(
		self,
		message: UserMessage,
		specialist_response: AgentResponse,
	) -> AgentResponse | None:
		"""Use runtime facts as grounding, then let the LLM write naturally."""
		raw_report = specialist_response.metadata.get("specialist_report")
		raw_results = specialist_response.metadata.get("tool_execution_results")
		sanitised_results = (
			[
				self.sanitise_device_execution_result(result)
				for result in raw_results
				if isinstance(result, dict)
			]
			if isinstance(raw_results, list)
			else []
		)
		fallback_text = (
			self.render_device_control_text(message.text, sanitised_results[0])
			if sanitised_results
			else self.render_device_specialist_fallback_text(
				message.text,
				specialist_response,
			)
		)
		payload = {
			"user_message": message.text,
			"route": "device_control",
			"specialist_report": raw_report if isinstance(raw_report, dict) else {},
			"execution_results": sanitised_results,
			"tool_runtime": specialist_response.metadata.get("tool_runtime", {}),
			"sensor_snapshot": self.mqtt.get_sensor_snapshot(),
			"current_time": self.build_time_context(),
			"recent_conversation": self.conversations.get(message.chat_id, [])[-4:],
		}
		text = await self.compose_text_with_llm(
			DEVICE_CONTROL_RESPONSE_SYSTEM,
			payload,
			fallback_text=fallback_text,
		)
		return AgentResponse(
			text=text,
			agent_name="orchestrator",
			tools_used=list(specialist_response.tools_used),
			confidence=specialist_response.confidence,
			metadata={
				"specialist_agent": specialist_response.agent_name,
				"user_visible_result": text,
				"specialist_report": raw_report if isinstance(raw_report, dict) else {},
				"tool_execution_results": sanitised_results,
			},
		)

	async def compose_natural_specialist_response(
		self,
		message: UserMessage,
		route_decision: RouteDecision,
		specialist_response: AgentResponse,
		*,
		system_prompt: str,
		fallback_text: str,
	) -> AgentResponse:
		payload = {
			"user_message": message.text,
			"route_decision": route_decision.model_dump(mode="json"),
			"specialist": self.sanitise_specialist_payload(specialist_response),
			"sensor_snapshot": self.mqtt.get_sensor_snapshot(),
			"current_time": self.build_time_context(),
			"recent_conversation": self.conversations.get(message.chat_id, [])[-4:],
		}
		text = await self.compose_text_with_llm(
			system_prompt,
			payload,
			fallback_text=fallback_text,
		)
		return AgentResponse(
			text=text,
			agent_name="orchestrator",
			tools_used=list(specialist_response.tools_used),
			confidence=specialist_response.confidence,
			metadata={
				"specialist_agent": specialist_response.agent_name,
				"user_visible_result": text,
				"specialist_report": specialist_response.metadata.get(
					"specialist_report", {}
				),
			},
		)

	async def compose_text_with_llm(
		self,
		system_prompt: str,
		payload: dict,
		*,
		fallback_text: str,
	) -> str:
		messages = [
			{"role": "system", "content": system_prompt},
			{
				"role": "user",
				"content": json.dumps(payload, ensure_ascii=False, indent=2),
			},
		]
		orchestrator_model = (
			self.orchestrator_model
			or runtime_settings.get_active_model(
				"orchestratorModel",
			)
		)
		try:
			result = await asyncio.wait_for(
				asyncio.to_thread(
					self.llm.completion,
					messages,
					None,
					orchestrator_model,
				),
				timeout=FINAL_RESPONSE_TIMEOUT_SECONDS,
			)
		except Exception as exc:
			log_compose(f"LLM composer fallback: {exc}")
			return fallback_text
		return clean_user_visible_text(result["content"] or fallback_text)

	async def compose_device_control_user_text(
		self,
		user_text: str,
		payload: dict,
	) -> str:
		return self.render_device_control_text(user_text, payload)

	@staticmethod
	def sanitise_device_execution_result(result: dict) -> dict:
		verification = result.get("verification")
		policy_decision = result.get("policy_decision")
		raw_metadata = result.get("raw_metadata")
		if not isinstance(raw_metadata, dict):
			raw_metadata = {}
		raw_proposal = raw_metadata.get("proposal")
		raw_arguments = (
			raw_proposal.get("arguments", {}) if isinstance(raw_proposal, dict) else {}
		)
		double_check_status = raw_metadata.get("double_check_status")
		return {
			"ok": result.get("ok"),
			"status": result.get("status"),
			"reason": result.get("reason"),
			"capability_name": result.get("capability_name"),
			"target": raw_metadata.get("target") or raw_arguments.get("device_target"),
			"arguments": raw_arguments,
			"after_state": result.get("after_state", {}),
			"changed_entities": result.get("changed_entities", []),
			"unchanged_entities": result.get("unchanged_entities", []),
			"failed_entities": result.get("failed_entities", []),
			"verification_status": (
				verification.get("status") if isinstance(verification, dict) else None
			),
			"policy_reason": (
				policy_decision.get("reason")
				if isinstance(policy_decision, dict)
				else None
			),
			"user_visible_message": (raw_metadata.get("user_visible_message")),
			"double_check_status": double_check_status,
		}

	@staticmethod
	def sanitise_pending_confirmation(pending: dict) -> dict:
		raw_proposal = pending.get("proposal", {})
		if not isinstance(raw_proposal, dict):
			raw_proposal = {}
		return {
			"capability_name": raw_proposal.get("capability_name"),
			"arguments": raw_proposal.get("arguments", {}),
			"reason": pending.get("reason"),
		}

	@staticmethod
	def sanitise_specialist_payload(response: AgentResponse) -> dict:
		report = response.metadata.get("specialist_report")
		if not isinstance(report, dict):
			report = {}
		return {
			"name": response.agent_name,
			"summary": report.get("summary"),
			"analysis_payload": report.get("analysis_payload", {}),
			"tools_used": list(response.tools_used),
		}
