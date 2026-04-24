"""Execution context passed into runtime services."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecutionContext(BaseModel):
	"""Request and route metadata for tool runtime execution."""

	model_config = ConfigDict(extra="forbid")

	request_id: str
	session_id: str
	user_id: str
	channel: str
	route_intent: str
	specialist: str
	metadata: dict[str, Any] = Field(default_factory=dict)
