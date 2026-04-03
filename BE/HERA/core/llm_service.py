"""
LLM Service
============
Provider-agnostic wrapper around Ollama (local) and OpenRouter (cloud).
Returns a normalised response dict regardless of backend.
"""

from __future__ import annotations

import json
import re
from typing import Any

import ollama
import openai

from config import (
    OLLAMA_MODEL, OLLAMA_ROUTER_MODEL,
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_BASE_URL,
)


# ── Hallucination filter ─────────────────────────────────────

_HALLUCINATION_MARKERS = (
    "![", "Image:", "Picture:", "Photo:",
    "http://192.168.", "LED_ON.jpeg", "specific color you'd like for",
)


def filter_response(text: str) -> str:
    """Strip hallucinated image URLs / markdown images."""
    if not text:
        return text
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'https?://[^\s]+\.(jpg|jpeg|png|gif)', '', text)
    if any(m in text for m in _HALLUCINATION_MARKERS):
        return "✅ Action completed successfully."
    return text.strip()


# ── Normalised result dict ────────────────────────────────────

LLMResult = dict[str, Any]  # {"content": str|None, "tool_calls": list|None}


# ── Service ───────────────────────────────────────────────────

class LLMService:
    """
    Stateless service — each call is independent.

    Parameters
    ----------
    provider : "ollama" | "openrouter"
    """

    def __init__(self, provider: str) -> None:
        self.provider = provider

    # ── public API ────────────────────────────────────────────

    def completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model_override: str | None = None,
    ) -> LLMResult:
        """
        Send *messages* to the configured LLM and return a normalised result.

        Parameters
        ----------
        model_override : use a specific model name (e.g. the small router model).
        """
        if self.provider == "ollama":
            return self._ollama(messages, tools, model_override)
        return self._openrouter(messages, tools, model_override)

    # ── Ollama ────────────────────────────────────────────────

    def _ollama(self, messages, tools, model_override) -> LLMResult:
        model = model_override or OLLAMA_MODEL
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = ollama.chat(**kwargs)
        msg = resp.message
        if not msg.tool_calls:
            return {"content": msg.content, "tool_calls": None}
        return {
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": f"call_{i}",
                    "name": tc.function.name,
                    "args": tc.function.arguments or {},
                }
                for i, tc in enumerate(msg.tool_calls)
            ],
        }

    # ── OpenRouter ────────────────────────────────────────────

    def _openrouter(self, messages, tools, model_override) -> LLMResult:
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is not set in .env")
        client = openai.OpenAI(
            base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY,
        )
        model = model_override or OPENROUTER_MODEL
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return {"content": msg.content, "tool_calls": None}
        return {
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "args": (
                        json.loads(tc.function.arguments)
                        if tc.function.arguments else {}
                    ),
                }
                for tc in msg.tool_calls
            ],
        }

    # ── Message builders (provider-aware) ─────────────────────

    def build_assistant_tool_msg(
        self, content: str, tool_calls: list[dict],
    ) -> dict:
        msg: dict = {"role": "assistant", "content": content}
        if self.provider == "openrouter":
            msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["args"]),
                    },
                }
                for tc in tool_calls
            ]
        else:
            msg["tool_calls"] = [
                {"function": {"name": tc["name"], "arguments": tc["args"]}}
                for tc in tool_calls
            ]
        return msg

    def build_tool_result_msg(self, tool_call_id: str, result: str) -> dict:
        msg: dict = {"role": "tool", "content": result}
        if self.provider == "openrouter":
            msg["tool_call_id"] = tool_call_id
        return msg
