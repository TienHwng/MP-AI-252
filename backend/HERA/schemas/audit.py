"""Audit and trace contracts for request lifecycle correlation."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class TraceContext(BaseModel):
	"""Correlation metadata shared across orchestration, tools, and audit."""

	model_config = ConfigDict(extra="forbid")

	trace_id: str = Field(default_factory=lambda: str(uuid4()))
	request_id: str
	parent_span_id: str | None = None
	created_at: datetime = Field(default_factory=datetime.now)
	metadata: dict[str, Any] = Field(default_factory=dict)
