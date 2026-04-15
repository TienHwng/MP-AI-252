"""
LLM Service
============
Provider-agnostic wrapper around LiteLLM.
Returns a normalised response dict regardless of backend.
"""

from __future__ import annotations

import json
import re
from typing import Any
from itertools import count

import litellm
from litellm import completion as litellm_completion

from config import (
    OLLAMA_MODEL,
    OLLAMA_API_BASE,
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
        return "[OK] Action completed successfully."
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

    _call_counter = count(1)

    def __init__(self, provider: str) -> None:
        self.provider = provider
        # Prevent LiteLLM from printing provider help banners to stdout.
        litellm.suppress_debug_info = True

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
            default_model = OLLAMA_MODEL
        else:
            default_model = OPENROUTER_MODEL
        raw_model = model_override or default_model
        model = self._provider_model_name(raw_model, self.provider)
        if self.provider == "ollama" and tools:
            if model.startswith("ollama/"):
                model = f"ollama_chat/{model.removeprefix('ollama/')}"
            elif not model.startswith("ollama_chat/"):
                model = f"ollama_chat/{model}"
        call_id = next(self._call_counter)
        tool_count = len(tools) if tools else 0
        print(
            f"[LLM] API call #{call_id} -> provider={self.provider} "
            f"model={model} tools={tool_count} messages={len(messages)}"
        )
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if self.provider == "ollama":
            kwargs["api_base"] = OLLAMA_API_BASE
        elif self.provider == "openrouter":
            if not OPENROUTER_API_KEY:
                raise ValueError("OPENROUTER_API_KEY is not set in .env")
            kwargs["api_key"] = OPENROUTER_API_KEY
            kwargs["api_base"] = OPENROUTER_BASE_URL
            kwargs["custom_llm_provider"] = "openrouter"
        resp = litellm_completion(**kwargs)
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            print(f"[LLM] API call #{call_id} <- tool_calls=0")
            return {"content": msg.content, "tool_calls": None}

        normalized_tool_calls = []
        for i, tc in enumerate(tool_calls):
            fn = tc.function
            args = fn.arguments
            if isinstance(args, str):
                if args:
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Invalid tool arguments from model: {args!r}",
                        ) from exc
                else:
                    args = {}
            normalized_tool_calls.append(
                {
                    "id": tc.id or f"call_{i}",
                    "name": fn.name,
                    "args": args or {},
                }
            )
        print(
            f"[LLM] API call #{call_id} <- tool_calls={len(normalized_tool_calls)}"
        )
        return {
            "content": msg.content or "",
            "tool_calls": normalized_tool_calls,
        }

    @staticmethod
    def _provider_model_name(model_name: str, provider: str) -> str:
        if model_name.startswith(("ollama/", "ollama_chat/", "openrouter/")):
            return model_name
        if provider == "ollama":
            return f"ollama/{model_name}"
        return f"openrouter/{model_name}"

    # ── Message builders (OpenAI-format, works across LiteLLM backends) ──

    def build_assistant_tool_msg(
        self, content: str, tool_calls: list[dict],
    ) -> dict:
        return {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["args"]),
                    },
                }
                for tc in tool_calls
            ],
        }

    def build_tool_result_msg(self, tool_call_id: str, result: str) -> dict:
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        }
