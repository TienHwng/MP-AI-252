"""
LLM Service
============
Provider-agnostic wrapper around LiteLLM.
Returns a normalised response dict regardless of backend.
"""

from __future__ import annotations

import json
import re
from itertools import count
from typing import Any

import litellm
from config import (
	OLLAMA_API_BASE,
	OPENROUTER_API_KEY,
	OPENROUTER_BASE_URL,
)
from litellm import completion as litellm_completion

from core.logger import log_error, log_llm
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
		try:
			resp = litellm_completion(**kwargs)
		except Exception as exc:
			error_info = self.describe_exception(exc)
			error_info.update(
				{
					"call": call_id,
					"provider": active_provider,
					"model": model,
				}
			)
			log_error(
				"LLM request failed",
				data={
					"call": call_id,
					"provider": active_provider,
					"model": model,
					"status": error_info.get("status") or "unknown",
					"type": error_info["type"],
				},
				detail=self.render_error_detail(error_info),
			)
			raise
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

	@staticmethod
	def describe_exception(exc: Exception) -> dict[str, Any]:
		text = str(exc)
		payload = LLMService.extract_json_payload(text)
		error = payload.get("error", {}) if isinstance(payload, dict) else {}
		metadata = error.get("metadata", {}) if isinstance(error, dict) else {}
		raw = metadata.get("raw") if isinstance(metadata, dict) else None
		raw_message = LLMService.extract_raw_message(raw)
		message = raw_message or error.get("message") or text

		return {
			"type": exc.__class__.__name__,
			"status": error.get("code") or getattr(exc, "status_code", None),
			"message": LLMService.compact_text(str(message)),
			"provider_name": metadata.get("provider_name") if isinstance(metadata, dict) else None,
			"is_byok": metadata.get("is_byok") if isinstance(metadata, dict) else None,
			"raw": LLMService.compact_text(str(raw)) if raw else None,
		}

	@staticmethod
	def extract_json_payload(text: str) -> dict[str, Any]:
		for match in re.finditer(r"\{", text):
			candidate = text[match.start() :].strip()
			try:
				payload = json.loads(candidate)
			except json.JSONDecodeError:
				continue
			if isinstance(payload, dict):
				return payload
		return {}

	@staticmethod
	def extract_raw_message(raw: Any) -> str | None:
		if not raw:
			return None
		if isinstance(raw, str):
			try:
				parsed = json.loads(raw)
			except json.JSONDecodeError:
				return raw
		else:
			parsed = raw
		if not isinstance(parsed, dict):
			return str(parsed)
		error = parsed.get("error")
		if isinstance(error, dict) and error.get("message"):
			return str(error["message"])
		return None

	@staticmethod
	def compact_text(text: str, limit: int = 360) -> str:
		compact = " ".join(text.split())
		if len(compact) <= limit:
			return compact
		return f"{compact[: limit - 3]}..."

	@staticmethod
	def render_error_detail(error_info: dict[str, Any]) -> str:
		lines = [
			f"reason: {error_info['message']}",
		]
		if error_info.get("provider_name"):
			lines.append(f"upstream: {error_info['provider_name']}")
		if error_info.get("is_byok") is not None:
			lines.append(f"byok: {error_info['is_byok']}")
		if error_info.get("raw") and error_info["raw"] != error_info["message"]:
			lines.append(f"raw: {error_info['raw']}")
		return "\n  | ".join(lines)

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
