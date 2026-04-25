"""
LLM Service
============
Provider-agnostic wrapper around LiteLLM.
Returns a normalised response dict regardless of backend.
"""

from __future__ import annotations

import json
from itertools import count
from typing import Any

import litellm
from config import (
	OLLAMA_API_BASE,
	OPENROUTER_API_KEY,
	OPENROUTER_BASE_URL,
)
from litellm import completion as litellm_completion

from core.logger import log_llm
from core.runtime_settings import runtime_settings

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

	call_counter = count(1)

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
		active_provider = runtime_settings.refresh_and_log()["provider"]
		fallback_model = runtime_settings.get_model(
			active_provider, "orchestratorModel"
		)
		if not fallback_model:
			raise ValueError(
				f"Missing runtime orchestrator model for provider '{active_provider}'.",
			)
		raw_model = model_override or fallback_model
		model = self.provider_model_name(raw_model, active_provider)
		if active_provider == "ollama" and tools:
			if model.startswith("ollama/"):
				model = f"ollama_chat/{model.removeprefix('ollama/')}"
			elif not model.startswith("ollama_chat/"):
				model = f"ollama_chat/{model}"
		call_id = next(self.call_counter)
		tool_count = len(tools) if tools else 0
		log_llm(
			f"API call #{call_id} → {model}",
			data={
				"provider": active_provider,
				"tools": tool_count,
				"msgs": len(messages),
			},
		)
		kwargs: dict[str, Any] = {
			"model": model,
			"messages": messages,
		}
		if tools:
			kwargs["tools"] = tools
			kwargs["tool_choice"] = "auto"
		if active_provider == "ollama":
			kwargs["api_base"] = OLLAMA_API_BASE
			kwargs["think"] = False  # Disable thinking chain for Ollama
		elif active_provider == "openrouter":
			if not OPENROUTER_API_KEY:
				raise ValueError("OPENROUTER_API_KEY is not set in .env")
			kwargs["api_key"] = OPENROUTER_API_KEY
			kwargs["api_base"] = OPENROUTER_BASE_URL
			kwargs["custom_llm_provider"] = "openrouter"
			kwargs["think"] = False  # Disable thinking chain for OpenRouter too
		resp = litellm_completion(**kwargs)
		msg = resp.choices[0].message

		tool_calls = getattr(msg, "tool_calls", None)
		if not tool_calls:
			log_llm(f"API call #{call_id} ← text response", data={"tool_calls": 0})
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
		tool_names = [tc["name"] for tc in normalized_tool_calls]
		log_llm(
			f"API call #{call_id} ← tool response",
			data={"tool_calls": len(normalized_tool_calls), "tools": tool_names},
		)
		return {
			"content": msg.content or "",
			"tool_calls": normalized_tool_calls,
		}

	@staticmethod
	def provider_model_name(model_name: str, provider: str) -> str:
		if model_name.startswith(("ollama/", "ollama_chat/", "openrouter/")):
			return model_name
		if provider == "ollama":
			return f"ollama/{model_name}"
		return f"openrouter/{model_name}"

	# ── Message builders (OpenAI-format, works across LiteLLM backends) ──

	def build_assistant_tool_msg(
		self,
		content: str,
		tool_calls: list[dict],
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
