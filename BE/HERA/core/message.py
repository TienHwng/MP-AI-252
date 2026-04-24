"""
Message types shared across the HERA pipeline.

These dataclasses define the contract between adapters (Telegram, Voice, REST)
and the agent layer.  Any new I/O adapter only needs to produce a
``UserMessage`` and consume an ``AgentResponse``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class MessageSource(StrEnum):
	TELEGRAM = "telegram"
	VOICE = "voice"
	REST = "rest"


@dataclass(slots=True)
class UserMessage:
	"""Canonical inbound message — adapter-agnostic."""

	text: str
	chat_id: str
	source: MessageSource
	timestamp: datetime = field(default_factory=datetime.now)
	request_id: str = field(default_factory=lambda: str(uuid4()))
	metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentResponse:
	"""Canonical outbound message returned by any agent."""

	text: str
	agent_name: str
	tools_used: list[str] = field(default_factory=list)
	confidence: float = 1.0
	metadata: dict[str, Any] = field(default_factory=dict)
