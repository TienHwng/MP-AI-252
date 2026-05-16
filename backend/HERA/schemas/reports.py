"""Specialist output contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from schemas.tooling import ToolProposal


class SpecialistReport(BaseModel):
	"""Structured specialist result before final user-facing composition."""

	model_config = ConfigDict(extra="forbid")

	specialist_name: str
	summary: str
	tool_proposals: list[ToolProposal] = Field(default_factory=list)
	clarification_question: str | None = None
	analysis_payload: dict[str, Any] = Field(default_factory=dict)
