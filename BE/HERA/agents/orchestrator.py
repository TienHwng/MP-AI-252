"""
Orchestrator Agent (Router / Mediator)
=======================================
Receives every user message, classifies intent, and delegates
to the appropriate specialist agent.

Uses a *small* language model (e.g. qwen2.5:1.5b) for fast routing,
then forwards to the specialist which may use a larger model.
"""

from __future__ import annotations

import asyncio
import json
import time

from agents.base import AgentBase
from core.llm_service import LLMService
from core.message import AgentResponse, UserMessage
from core.language_policy import detect_user_language
from config import (
    ORCHESTRATOR_MODEL_OLLAMA,
    ORCHESTRATOR_MODEL_OPENROUTER,
    MAX_HISTORY,
)

# ── Intent taxonomy ───────────────────────────────────────────

INTENTS = (
    "device_control",   # turn on/off LED, actuator commands
    "sensor_query",     # what is the temperature / humidity / status
    "anomaly_query",    # is there an anomaly, why is the score high
    "general",          # greetings, help, chitchat, FAQ
)

_ROUTER_SYSTEM = """\
You are an intent classifier for a smart-home IoT assistant called HERA.
Given the user message, output EXACTLY ONE of the following labels — nothing else:

  device_control  — user wants to turn on/off/toggle a light, LED, or actuator
  sensor_query    — user asks about temperature, humidity, sensor status, readings
  anomaly_query   — user asks about anomalies, abnormalities, ML detection, warnings
  general         — greetings, help, what-can-you-do, chitchat, anything else

Respond with ONLY the label. No explanation, no punctuation.
"""


class Orchestrator:
    """
    Central mediator — not itself an ``AgentBase`` because it *delegates*
    rather than generating a final user-facing response.
    """

    def __init__(
        self,
        llm: LLMService,
        agents: dict[str, AgentBase],
        *,
        router_model: str | None = None,
    ) -> None:
        self._llm = llm
        self._agents = agents
        default_router = (
            ORCHESTRATOR_MODEL_OLLAMA
            if llm.provider == "ollama"
            else ORCHESTRATOR_MODEL_OPENROUTER
        )
        self._router_model = router_model or default_router
        # per-chat conversation history (only for chat agent)
        self._conversations: dict[str, list[dict]] = {}

    # ── public entry point ────────────────────────────────────

    async def handle(self, message: UserMessage) -> AgentResponse:
        """Classify → route → return specialist response."""
        t0 = time.perf_counter()

        intent = await self._classify_intent(message.text)
        agent_key = self._intent_to_agent(intent)
        agent = self._agents.get(agent_key)

        if agent is None:
            agent = self._agents["chat"]

        print(
            f"[Orchestrator] intent={intent!r} → agent={agent.name!r}"
        )

        # build shared context
        chat_id = message.chat_id
        if chat_id not in self._conversations:
            self._conversations[chat_id] = []
        target_language = detect_user_language(message.text)
        context = {
            "history": self._conversations[chat_id],
            "target_language": target_language,
        }

        response = await agent.process(message, context)

        # history management
        if response.tools_used:
            # reset after tool use to avoid context pollution
            self._conversations[chat_id] = []
        else:
            self._conversations[chat_id].append(
                {"role": "user", "content": message.text},
            )
            self._conversations[chat_id].append(
                {"role": "assistant", "content": response.text},
            )
            if len(self._conversations[chat_id]) > MAX_HISTORY:
                self._conversations[chat_id] = (
                    self._conversations[chat_id][-MAX_HISTORY:]
                )

        elapsed = time.perf_counter() - t0
        response.metadata["latency_s"] = round(elapsed, 2)
        response.metadata["intent"] = intent
        response.metadata["target_language"] = target_language
        print(f"[Orchestrator] done in {elapsed:.2f}s")

        return response

    def reset_history(self, chat_id: str) -> None:
        self._conversations.pop(chat_id, None)

    # ── intent classification ─────────────────────────────────

    async def _classify_intent(self, text: str) -> str:
        """Use a small LLM to classify user intent."""
        messages = [
            {"role": "system", "content": _ROUTER_SYSTEM},
            {"role": "user", "content": text},
        ]
        result = await asyncio.to_thread(
            self._llm.completion,
            messages,
            None,
            self._router_model,
        )
        raw = (result["content"] or "general").strip().lower()
        # extract first matching intent label from response
        for intent in INTENTS:
            if intent in raw:
                return intent
        return "general"

    # ── mapping ───────────────────────────────────────────────

    @staticmethod
    def _intent_to_agent(intent: str) -> str:
        return {
            "device_control": "device_control",
            "sensor_query":   "sensor_analysis",
            "anomaly_query":  "anomaly_expert",
            "general":        "chat",
        }.get(intent, "chat")
