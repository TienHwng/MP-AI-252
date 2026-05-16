"""Memory write contracts used by later Mongo-backed memory phases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActionSummary(BaseModel):
	"""Compact post-action memory record for follow-up control."""

	model_config = ConfigDict(extra="forbid")

	request_id: str
	user_id: str
	session_id: str
	original_text: str
	interpreted_action: str
	interpreted_targets: list[str] = Field(default_factory=list)
	result_status: str
	verification_status: str = "unknown"
	timestamp: datetime = Field(default_factory=datetime.now)
	policy_decision: str | None = None
	changed_entities: list[str] = Field(default_factory=list)
	unchanged_entities: list[str] = Field(default_factory=list)
	failed_entities: list[str] = Field(default_factory=list)
	runtime_context: dict[str, Any] = Field(default_factory=dict)


class SessionTurn(BaseModel):
	"""Compact conversation turn retained per session."""

	model_config = ConfigDict(extra="forbid")

	request_id: str
	session_id: str
	user_id: str
	channel: str
	user_text: str
	assistant_text: str
	intent: str
	tools_used: list[str] = Field(default_factory=list)
	timestamp: datetime = Field(default_factory=datetime.now)


class MemoryContext(BaseModel):
	"""Retrieved memory bundle injected into orchestration."""

	model_config = ConfigDict(extra="forbid")

	available: bool
	reason: str | None = None
	recent_turns: list[dict[str, Any]] = Field(default_factory=list)
	recent_actions: list[dict[str, Any]] = Field(default_factory=list)
	user_profile: dict[str, Any] = Field(default_factory=dict)
