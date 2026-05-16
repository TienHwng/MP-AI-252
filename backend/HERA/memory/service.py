"""High-level structured memory service used by the orchestrator."""

from __future__ import annotations

from datetime import datetime

from config import MEMORY_RECENT_ACTION_LIMIT, MEMORY_SESSION_TURN_LIMIT
from core.message import AgentResponse
from runtime import ExecutionContext
from schemas import (
	ActionSummary,
	IncomingRequest,
	MemoryContext,
	SessionTurn,
	ToolExecutionResult,
)

from memory.action_summary_store import ActionSummaryStore
from memory.mongo_client import MongoMemoryClient
from memory.profile_store import ProfileStore
from memory.retrieval_service import RetrievalService
from memory.session_store import SessionStore


class MemoryService:
	"""Coordinates Mongo-backed memory reads and writes."""

	def __init__(
		self,
		mongo: MongoMemoryClient,
		*,
		recent_action_limit: int = MEMORY_RECENT_ACTION_LIMIT,
		session_turn_limit: int = MEMORY_SESSION_TURN_LIMIT,
	) -> None:
		self.mongo = mongo
		self.sessions = SessionStore(mongo, turn_limit=session_turn_limit)
		self.actions = ActionSummaryStore(mongo)
		self.profiles = ProfileStore(mongo)
		self.retrieval = RetrievalService(
			self.sessions,
			self.actions,
			self.profiles,
			recent_action_limit=recent_action_limit,
		)
		self._ensure_indexes()

	def retrieve(self, request: IncomingRequest) -> MemoryContext:
		return self.retrieval.retrieve(request, available=self.mongo.available)

	def retrieve_scoped(
		self,
		request: IncomingRequest,
		scopes: set[str],
	) -> MemoryContext:
		return self.retrieval.retrieve(
			request,
			available=self.mongo.available,
			scopes=scopes,
		)

	def record_turn(
		self,
		request: IncomingRequest,
		response: AgentResponse,
		*,
		intent: str,
	) -> bool:
		turn = SessionTurn(
			request_id=request.request_id,
			session_id=request.session_id,
			user_id=request.user_id,
			channel=request.channel,
			user_text=request.text,
			assistant_text=response.text,
			intent=intent,
			tools_used=list(response.tools_used),
		)
		return self.sessions.append_turn(turn)

	def record_tool_results(
		self,
		request: IncomingRequest,
		context: ExecutionContext,
		results: list[ToolExecutionResult],
		*,
		original_text: str,
	) -> list[ActionSummary]:
		written: list[ActionSummary] = []
		for result in results:
			targets = self._targets_from_result(result)
			summary = ActionSummary(
				request_id=request.request_id,
				user_id=request.user_id,
				session_id=request.session_id,
				original_text=original_text,
				interpreted_action=result.capability_name,
				interpreted_targets=targets,
				result_status=result.status,
				verification_status=result.verification.status,
				timestamp=datetime.now(),
				policy_decision=(
					result.policy_decision.decision if result.policy_decision else None
				),
				changed_entities=list(result.changed_entities),
				unchanged_entities=list(result.unchanged_entities),
				failed_entities=list(result.failed_entities),
				runtime_context=context.model_dump(mode="json"),
			)
			if self.actions.insert(summary):
				written.append(summary)
		return written

	def _ensure_indexes(self) -> None:
		self.mongo.ensure_indexes(
			{
				"session_threads": [
					([("session_id", 1), ("user_id", 1)], {"unique": True}),
					([("updated_at", -1)], {}),
				],
				"action_summaries": [
					([("session_id", 1), ("user_id", 1), ("timestamp", -1)], {}),
					([("request_id", 1)], {}),
				],
				"user_profiles": [
					([("user_id", 1)], {"unique": True}),
				],
			}
		)

	@staticmethod
	def _targets_from_result(result: ToolExecutionResult) -> list[str]:
		targets = [
			*result.changed_entities,
			*result.unchanged_entities,
			*result.failed_entities,
		]
		if targets:
			return list(dict.fromkeys(str(item) for item in targets))
		raw_target = result.raw_metadata.get("target")
		if raw_target is not None:
			return [str(raw_target)]
		raw_proposal = result.raw_metadata.get("proposal")
		if isinstance(raw_proposal, dict):
			args = raw_proposal.get("arguments")
			if isinstance(args, dict):
				for key in ("device_target", "light_target"):
					if args.get(key) is not None:
						return [str(args[key])]
		return []
