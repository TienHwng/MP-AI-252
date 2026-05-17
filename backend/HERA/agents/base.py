"""Structural specialist-agent protocol used by the orchestrator."""

from __future__ import annotations

from typing import Protocol

from core.message import AgentResponse, UserMessage


class AgentLike(Protocol):
	"""Any object with this shape can be mounted as a HERA specialist."""

	@property
	def name(self) -> str:
		"""Short identifier, e.g. ``'device_control'``."""

	@property
	def description(self) -> str:
		"""One-line summary used by the orchestrator prompt."""

	async def process(
		self,
		message: UserMessage,
		context: dict,
	) -> AgentResponse:
		"""
		Handle *message* and return a response.

		Parameters
		----------
		context : mutable dict carrying ``sensor_state``, ``history``, etc.
		"""
