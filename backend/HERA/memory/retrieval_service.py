"""Memory retrieval facade for orchestrator and specialists."""

from __future__ import annotations

from schemas import IncomingRequest, MemoryContext

from memory.action_summary_store import ActionSummaryStore
from memory.profile_store import ProfileStore
from memory.session_store import SessionStore


class RetrievalService:
	def __init__(
		self,
		sessions: SessionStore,
		actions: ActionSummaryStore,
		profiles: ProfileStore,
		*,
		recent_action_limit: int,
	) -> None:
		self.sessions = sessions
		self.actions = actions
		self.profiles = profiles
		self.recent_action_limit = recent_action_limit

	def retrieve(
		self,
		request: IncomingRequest,
		*,
		available: bool,
		scopes: set[str] | None = None,
	) -> MemoryContext:
		if not available:
			return MemoryContext(
				available=False,
				reason="mongo_unavailable",
			)
		scopes = scopes or {"session", "actions", "profile"}
		return MemoryContext(
			available=True,
			recent_turns=(
				self.sessions.get_recent_turns(
					request.session_id,
					request.user_id,
				)
				if "session" in scopes
				else []
			),
			recent_actions=(
				self.actions.recent_for_session(
					request.session_id,
					request.user_id,
					self.recent_action_limit,
				)
				if "actions" in scopes
				else []
			),
			user_profile=(
				self.profiles.get_profile(request.user_id)
				if "profile" in scopes
				else {}
			),
		)
