"""
Orchestrator Agent (Router / Mediator)
=======================================
Receives every user message, classifies intent, and delegates
to the appropriate specialist agent.

Uses the configured orchestrator model for intent routing and general
conversation, then forwards specialist requests to the relevant agent.
"""

from __future__ import annotations

import asyncio
import json
import time

from agents.base import AgentBase
from core.llm_service import LLMService
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService
from core.runtime_settings import runtime_settings
from config import (
    MAX_HISTORY,
)

# ── Intent taxonomy ───────────────────────────────────────────

INTENTS = (
    "device_control",   # turn on/off LED, actuator commands
    "sensor_query",     # what is the temperature / humidity / status
    "anomaly_query",    # is there an anomaly, why is the score high
    "general",          # greetings, help, chitchat, FAQ
)

ROUTER_SYSTEM = """\
You are an intent classifier for a smart-home IoT assistant called HERA.
Given the user message, output EXACTLY ONE of the following labels — nothing else:

  device_control  — user wants to turn on/off/toggle a light, LED, fan, relay, or actuator
  sensor_query    — user asks about temperature, humidity, sensor status, readings
  anomaly_query   — user asks about anomalies, abnormalities, ML detection, warnings
  general         — greetings, help, what-can-you-do, chitchat, anything else

Respond with ONLY the label. No explanation, no punctuation.
"""

GENERAL_SYSTEM = """\
You are HERA (Home Environment & Response Assistant), the sophisticated yet
warm heart of a modern smart-home system.

### Personality
- You are knowledgeable, reliable, concise, and warmly helpful.
- You sound like a capable home assistant, not a cold machine.

### What you can help with
- General questions about the H.E.R.A system
- Explain how the sensors, LEDs, actuators, and anomaly detection work
- Chitchat, greetings, and help requests

### Current sensor snapshot
{sensor_context}

### Rules
- Always respond in the same language as the user.
- If the user asks to control a device or query sensors, say briefly that you
  can handle that and ask them to make the request directly.
- Never output Chinese/Mandarin characters or phrases.
"""

FINAL_RESPONSE_SYSTEM = """\
You are HERA's central orchestrator and final response composer.
The specialist agent may have already parsed the request, read telemetry, or
executed a hardware command. Your job is to write the final Telegram reply to
the user.

Rules:
- Always respond in the same language as the user.
- Use the specialist result as factual ground truth.
- Do not mention internal agent names, JSON, tools, MQTT, RPC, prompts, logs,
  metadata, or hidden checks.
- If a device command was executed, confirm it naturally.
- If no device command was sent because the requested state was already true,
  say that naturally.
- If only part of a grouped command changed, mention that briefly.
- If the report contains sensor data, answer with the relevant readings and
  compare them to the provided reference range when useful.
- If the report contains anomaly classification, explain the status, severity,
  likely cause, and recommendation using that classification as ground truth.
- If the specialist result is ambiguous or invalid, ask one concise
  clarification.
- Keep the response concise, natural, and user-facing.
- Never output Chinese/Mandarin characters or phrases.
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
        mqtt: MQTTService,
        *,
        orchestrator_model: str | None = None,
    ) -> None:
        self.llm = llm
        self.agents = agents
        self.mqtt = mqtt
        self.orchestrator_model = orchestrator_model
        # per-chat conversation history for general conversation
        self.conversations: dict[str, list[dict]] = {}

    # ── public entry point ────────────────────────────────────

    async def handle(self, message: UserMessage) -> AgentResponse:
        """Classify → route → return specialist response."""
        t0 = time.perf_counter()

        intent = await self.classify_intent(message.text)
        chat_id = message.chat_id
        if chat_id not in self.conversations:
            self.conversations[chat_id] = []

        if intent == "general":
            print("[Orchestrator] intent='general' → agent='orchestrator'")
            response = await self.handle_general(message)
        else:
            agent_key = self.intent_to_agent(intent)
            agent = self.agents.get(agent_key)

            if agent is None:
                print(
                    f"[Orchestrator] intent={intent!r} → agent='orchestrator'"
                )
                response = await self.handle_general(message)
            else:
                print(
                    f"[Orchestrator] intent={intent!r} → agent={agent.name!r}"
                )
                specialist_response = await agent.process(
                    message,
                    {"history": self.conversations[chat_id]},
                )
                response = await self.compose_final_response(
                    message,
                    intent,
                    specialist_response,
                )

        # history management
        if response.tools_used:
            # reset after tool use to avoid context pollution
            self.conversations[chat_id] = []
        else:
            self.conversations[chat_id].append(
                {"role": "user", "content": message.text},
            )
            self.conversations[chat_id].append(
                {"role": "assistant", "content": response.text},
            )
            if len(self.conversations[chat_id]) > MAX_HISTORY:
                self.conversations[chat_id] = (
                    self.conversations[chat_id][-MAX_HISTORY:]
                )

        elapsed = time.perf_counter() - t0
        response.metadata["latency_s"] = round(elapsed, 2)
        response.metadata["intent"] = intent
        print(f"[Orchestrator] done in {elapsed:.2f}s")

        return response

    def reset_history(self, chat_id: str) -> None:
        self.conversations.pop(chat_id, None)

    # ── intent classification ─────────────────────────────────

    async def classify_intent(self, text: str) -> str:
        """Use a small LLM to classify user intent."""
        messages = [
            {"role": "system", "content": ROUTER_SYSTEM},
            {"role": "user", "content": text},
        ]
        orchestrator_model = self.orchestrator_model or runtime_settings.get_active_model(
            "orchestratorModel",
        )
        result = await asyncio.to_thread(
            self.llm.completion,
            messages,
            None,
            orchestrator_model,
        )
        raw = (result["content"] or "general").strip().lower()
        # extract first matching intent label from response
        for intent in INTENTS:
            if intent in raw:
                return intent
        return "general"

    async def handle_general(self, message: UserMessage) -> AgentResponse:
        """Use the orchestrator model directly for general conversation."""
        history = self.conversations.get(message.chat_id, [])
        sensor_context = json.dumps(self.mqtt.get_sensor_snapshot(), indent=2)
        messages = [
            {
                "role": "system",
                "content": GENERAL_SYSTEM.format(sensor_context=sensor_context),
            },
            *history[-MAX_HISTORY:],
            {"role": "user", "content": message.text},
        ]
        orchestrator_model = self.orchestrator_model or runtime_settings.get_active_model(
            "orchestratorModel",
        )
        result = await asyncio.to_thread(
            self.llm.completion,
            messages,
            None,
            orchestrator_model,
        )
        return AgentResponse(
            text=(result["content"] or "(no response)").strip(),
            agent_name="orchestrator",
        )

    async def compose_final_response(
        self,
        message: UserMessage,
        intent: str,
        specialist_response: AgentResponse,
    ) -> AgentResponse:
        """Convert a specialist report into the final user-facing reply."""
        payload = {
            "user_message": message.text,
            "intent": intent,
            "specialist": {
                "name": specialist_response.agent_name,
                "report": specialist_response.text,
                "tools_used": specialist_response.tools_used,
                "metadata": specialist_response.metadata,
            },
            "sensor_snapshot": self.mqtt.get_sensor_snapshot(),
        }
        messages = [
            {"role": "system", "content": FINAL_RESPONSE_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, indent=2),
            },
        ]
        orchestrator_model = self.orchestrator_model or runtime_settings.get_active_model(
            "orchestratorModel",
        )
        result = await asyncio.to_thread(
            self.llm.completion,
            messages,
            None,
            orchestrator_model,
        )
        final_text = (result["content"] or specialist_response.text).strip()
        return AgentResponse(
            text=final_text,
            agent_name="orchestrator",
            tools_used=list(specialist_response.tools_used),
            confidence=specialist_response.confidence,
            metadata={
                "specialist_agent": specialist_response.agent_name,
                "specialist_report": specialist_response.text,
                "specialist_metadata": specialist_response.metadata,
            },
        )

    # ── mapping ───────────────────────────────────────────────

    @staticmethod
    def intent_to_agent(intent: str) -> str:
        return {
            "device_control": "device_control",
            "sensor_query":   "sensor_analysis",
            "anomaly_query":  "anomaly_expert",
        }.get(intent, "")
