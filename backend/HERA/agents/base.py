"""
Agent Base
==========
Abstract base class that every HERA agent must implement.

The protocol is intentionally simple:
  1.  ``name`` / ``description`` — identity for logging & orchestration
  2.  ``process(message, context)`` — takes a user message, returns a response
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.message import AgentResponse, UserMessage


class AgentBase(ABC):
    """Contract that all specialist agents fulfil."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. ``'device_control'``."""

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line summary used by the orchestrator prompt."""

    @abstractmethod
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
