"""Inbound request contracts for adapter-independent orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from core.message import UserMessage
from pydantic import BaseModel, ConfigDict, Field


class IncomingRequest(BaseModel):
	"""Canonical request object used after an adapter receives input."""

	model_config = ConfigDict(extra="forbid")

	request_id: str = Field(default_factory=lambda: str(uuid4()))
	channel: str
	user_id: str
	session_id: str
	text: str = Field(min_length=1)
	timestamp: datetime = Field(default_factory=datetime.now)
	metadata: dict[str, Any] = Field(default_factory=dict)

	@classmethod
	def from_user_message(cls, message: UserMessage) -> IncomingRequest:
		return cls(
			request_id=message.request_id,
			channel=str(message.source),
			user_id=message.metadata.get("user_id", message.chat_id),
			session_id=message.chat_id,
			text=message.text,
			timestamp=message.timestamp,
			metadata={
				"chat_id": message.chat_id,
				**message.metadata,
			},
		)
