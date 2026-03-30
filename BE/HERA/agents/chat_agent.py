"""
Chat Agent (General Conversation)
==================================
Handles greetings, help requests, FAQ, and anything that doesn't
fall into device-control / sensor / anomaly categories.
"""

from __future__ import annotations

import asyncio
import json

from agents.base import AgentBase
from core.llm_service import LLMService, filter_response
from core.language_policy import build_language_policy, enforce_language_output
from core.message import AgentResponse, UserMessage
from core.mqtt_service import MQTTService
from config import (
    MAX_HISTORY,
    CHAT_AGENT_MODEL_OLLAMA,
    CHAT_AGENT_MODEL_OPENROUTER,
)

SYSTEM_PROMPT = """\
You are HERA, a friendly AI assistant for an IoT smart-home system.

### What you can help with
- General questions about the H.E.R.A system
- Explain how the sensors / LEDs / anomaly detection work
- Chitchat and greetings

### Current sensor snapshot (FYI)
{sensor_context}

### Rules
- ALWAYS respond in the SAME LANGUAGE as the user
- Be concise, friendly, and helpful
- If the user asks to control a device or query sensors, tell them
  you'll route the request appropriately (the orchestrator handles this)
- NEVER output Chinese/Mandarin
- NEVER generate image URLs or markdown images
"""


class ChatAgent(AgentBase):
    def __init__(self, llm: LLMService, mqtt: MQTTService) -> None:
        self._llm = llm
        self._mqtt = mqtt
        self._model_override = (
            CHAT_AGENT_MODEL_OLLAMA
            if llm.provider == "ollama"
            else CHAT_AGENT_MODEL_OPENROUTER
        )

    @property
    def name(self) -> str:
        return "chat"

    @property
    def description(self) -> str:
        return "General conversation, greetings, help, and FAQ."

    async def process(
        self, message: UserMessage, context: dict,
    ) -> AgentResponse:
        target_language = context.get("target_language", "en")
        history = context.get("history", [])
        system_prompt = (
            SYSTEM_PROMPT.format(
                sensor_context=json.dumps(
                    self._mqtt.get_sensor_snapshot(), indent=2,
                ),
            )
            + "\n\n"
            + build_language_policy(target_language)
        )

        messages = [
            {"role": "system", "content": system_prompt},
            *history[-MAX_HISTORY:],
            {"role": "user", "content": message.text},
        ]

        result = await asyncio.to_thread(
            self._llm.completion, messages, None, self._model_override,
        )
        reply = enforce_language_output(
            filter_response(result["content"] or "(no response)"),
            target_language,
        )

        return AgentResponse(text=reply, agent_name=self.name)
