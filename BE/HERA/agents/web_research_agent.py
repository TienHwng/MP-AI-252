"""Web research agent backed by the configured search provider."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Any

from core.logger import log_agent
from core.message import AgentResponse, UserMessage
from schemas import SpecialistReport
from web_search.intent_classifier import SearchIntentClassifier

URL_RE = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.IGNORECASE)
DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
MAX_SEARCH_SNIPPET_CHARS = 1200
MAX_FETCH_CONTENT_CHARS = 6000
WEATHER_MARKERS = (
	"weather",
	"forecast",
	"rain",
	"thời tiết",
	"thoi tiet",
	"dự báo",
	"du bao",
	"mưa",
	"mua",
)
TOMORROW_MARKERS = ("tomorrow", "ngày mai", "ngay mai", "mai")
VIETNAMESE_MARKERS = (
	"đ",
	"thời tiết",
	"ngày mai",
	"mai",
	"mưa",
	"không nhỉ",
)


def looks_like_vietnamese(text: str) -> bool:
	normalized = (text or "").lower()
	return any(marker in normalized for marker in VIETNAMESE_MARKERS)


class WebResearchAgent:
	"""Runs bounded web search/fetch work and returns structured evidence."""

	def __init__(
		self,
		search_service,
		max_results: int = 5,
		fetch_top_result: bool = True,
		intent_classifier: SearchIntentClassifier | None = None,
		specialized_services: dict[str, Any] | None = None,
	) -> None:
		self.search_service = search_service
		self.max_results = max_results
		self.fetch_top_result = fetch_top_result
		self.intent_classifier = intent_classifier or SearchIntentClassifier()
		self.specialized_services = specialized_services or {}

	@property
	def name(self) -> str:
		return "web_research"

	@property
	def description(self) -> str:
		return "Searches the web or fetches a URL through the configured provider."

	async def process(
		self,
		message: UserMessage,
		context: dict,
	) -> AgentResponse:
		route_plan = context.get("route_plan", {})
		if not isinstance(route_plan, dict):
			route_plan = {}
		query = self._query_from_route_plan(route_plan, message.text, context)
		url = self._extract_url(message.text)

		if url:
			tool_calls = [
				{
					"name": "fetch_web_page",
					"args": {"url": url},
					"confidence": 1.0,
					"source": "web_research_subgraph",
				}
			]
			result = await asyncio.to_thread(self.search_service.fetch, url)
			mode = "fetch"
			trimmed_fetch = self._trim_fetch_result(result)
			analysis_payload = {
				"mode": mode,
				"tool_calls": tool_calls,
				"tool_results": [
					{
						"name": "fetch_web_page",
						"ok": result.get("status") == "ok",
						"result": trimmed_fetch,
					}
				],
				"requested_url": url,
				"fetch": trimmed_fetch,
			}
		else:
			search_intent = self.intent_classifier.classify(query)
			if search_intent.intent != "generic":
				analysis_payload = await self._specialized_search(
					search_intent.intent,
					search_intent.parameters,
					query,
					message,
				)
				if analysis_payload is not None:
					mode = "search"
					summary = self._summary(mode, analysis_payload)
					specialist_report = SpecialistReport(
						specialist_name=self.name,
						summary=summary,
						analysis_payload=analysis_payload,
					)
					report = {
						"user_message": message.text,
						"web_research": analysis_payload,
						"specialist_report": specialist_report.model_dump(mode="json"),
					}
					log_agent(
						"WebResearch: specialized search complete",
						data=self._log_data(mode, analysis_payload),
					)
					return AgentResponse(
						text=json.dumps(report, ensure_ascii=False),
						agent_name=self.name,
						metadata=report,
					)

			tool_calls = [
				{
					"name": "search_web",
					"args": {"query": query, "max_results": self.max_results},
					"confidence": 1.0,
					"source": "web_research_subgraph",
				}
			]
			result = await asyncio.to_thread(
				self.search_service.search,
				query,
				self.max_results,
			)
			trimmed_search = self._trim_search_result(result)
			top_fetch = await self._fetch_top_result(trimmed_search)
			mode = "search"
			analysis_payload = {
				"mode": mode,
				"search_intent": {
					"intent": search_intent.intent,
					"confidence": search_intent.confidence,
					"reason": search_intent.reason,
					"parameters": search_intent.parameters,
				},
				"tool_calls": tool_calls,
				"tool_results": [
					{
						"name": "search_web",
						"ok": result.get("status") == "ok",
						"result": trimmed_search,
					},
				],
				"query": query,
				"search": trimmed_search,
				"top_fetch": top_fetch,
			}

		summary = self._summary(mode, analysis_payload)
		specialist_report = SpecialistReport(
			specialist_name=self.name,
			summary=summary,
			analysis_payload=analysis_payload,
		)
		report = {
			"user_message": message.text,
			"web_research": analysis_payload,
			"specialist_report": specialist_report.model_dump(mode="json"),
		}
		log_agent(
			f"WebResearch: {mode} complete",
			data=self._log_data(mode, analysis_payload),
		)
		return AgentResponse(
			text=json.dumps(report, ensure_ascii=False),
			agent_name=self.name,
			metadata=report,
		)

	async def _specialized_search(
		self,
		intent: str,
		parameters: dict[str, Any],
		query: str,
		message: UserMessage,
	) -> dict[str, Any] | None:
		service = self.specialized_services.get(intent)
		if service is None:
			return None

		tool_name = f"search_{intent}"
		tool_calls = [
			{
				"name": tool_name,
				"args": parameters,
				"confidence": 1.0,
				"source": "web_research_subgraph",
			}
		]
		result = await asyncio.to_thread(
			self._call_specialized_service,
			intent,
			service,
			parameters,
			query,
			message,
		)
		trimmed = self._trim_search_result(result)
		if trimmed.get("status") == "ok":
			return {
				"mode": "search",
				"search_intent": {
					"intent": intent,
					"confidence": 1.0,
					"reason": "specialized_service",
					"parameters": parameters,
				},
				"tool_calls": tool_calls,
				"tool_results": [
					{"name": tool_name, "ok": True, "result": trimmed},
				],
				"query": query,
				"search": trimmed,
				"top_fetch": {
					"available": False,
					"reason": "specialized_structured_result",
				},
			}

		fallback_result = await asyncio.to_thread(
			self.search_service.search,
			query,
			self.max_results,
		)
		trimmed_fallback = self._trim_search_result(fallback_result)
		top_fetch = await self._fetch_top_result(trimmed_fallback)
		return {
			"mode": "search",
			"search_intent": {
				"intent": intent,
				"confidence": 1.0,
				"reason": "specialized_service_fallback",
				"parameters": parameters,
			},
			"tool_calls": [
				*tool_calls,
				{
					"name": "search_web",
					"args": {"query": query, "max_results": self.max_results},
					"confidence": 1.0,
					"source": "web_research_subgraph",
				},
			],
			"tool_results": [
				{
					"name": tool_name,
					"ok": False,
					"result": trimmed,
				},
				{
					"name": "search_web",
					"ok": fallback_result.get("status") == "ok",
					"result": trimmed_fallback,
				},
			],
			"query": query,
			"search": trimmed_fallback,
			"specialized_error": trimmed,
			"top_fetch": top_fetch,
		}

	@staticmethod
	def _call_specialized_service(
		intent: str,
		service: Any,
		parameters: dict[str, Any],
		query: str,
		message: UserMessage,
	) -> dict[str, Any]:
		if intent == "weather":
			return service.forecast(
				parameters.get("location"),
				parameters.get("days_ahead", 0),
			)
		if intent == "calendar":
			return service.events(
				getattr(message, "chat_id", None),
				parameters.get("days_ahead", 0),
			)
		if intent == "news":
			return service.search(
				parameters.get("query") or query,
				country=parameters.get("country"),
				category=parameters.get("category"),
				max_results=5,
			)
		if intent == "price":
			return service.search(parameters.get("query") or query)
		if intent == "places":
			return service.search(
				parameters.get("query") or query,
				location=parameters.get("location"),
				category=parameters.get("category"),
				max_results=5,
			)
		return {
			"available": False,
			"status": "unavailable",
			"provider": intent,
			"reason": "unsupported_specialized_intent",
			"results": [],
		}

	@staticmethod
	def _query_from_route_plan(route_plan: dict, fallback: str, context: dict) -> str:
		query = route_plan.get("web_query")
		if isinstance(query, str) and query.strip():
			base_query = " ".join(query.split())
		else:
			base_query = " ".join((fallback or "").split())
		return WebResearchAgent._ground_time_location_query(
			base_query,
			fallback,
			context,
		)

	@staticmethod
	def _ground_time_location_query(query: str, user_text: str, context: dict) -> str:
		combined = f"{query} {user_text}".lower()
		if not any(marker in combined for marker in WEATHER_MARKERS):
			return query
		default_location = str(context.get("default_search_location") or "").strip()
		date_match = DATE_RE.search(query)
		date_text = date_match.group(0) if date_match else None
		if date_text is None and any(marker in combined for marker in TOMORROW_MARKERS):
			tomorrow = datetime.now().astimezone() + timedelta(days=1)
			date_text = tomorrow.strftime("%d/%m/%Y")
		if looks_like_vietnamese(user_text):
			location = default_location or "Ho Chi Minh City, Vietnam"
			date_part = f" ngày {date_text}" if date_text else ""
			return f"dự báo thời tiết {location}{date_part} khả năng mưa"
		parts = [query]
		if default_location and default_location.lower() not in query.lower():
			parts.append(default_location)
		if date_text and date_text not in query:
			parts.append(date_text)
		return " ".join(part for part in parts if part).strip()

	async def _fetch_top_result(self, search_result: dict[str, Any]) -> dict[str, Any]:
		if not self.fetch_top_result or search_result.get("status") != "ok":
			return {"available": False, "reason": "top_fetch_disabled"}
		results = search_result.get("results", [])
		if not isinstance(results, list) or not results:
			return {"available": False, "reason": "no_search_results"}
		top = results[0]
		if not isinstance(top, dict):
			return {"available": False, "reason": "invalid_top_result"}
		url = str(top.get("url") or "").strip()
		if not url:
			return {"available": False, "reason": "missing_top_result_url"}
		result = await asyncio.to_thread(self.search_service.fetch, url)
		return self._trim_fetch_result(result)

	@staticmethod
	def _extract_url(text: str) -> str | None:
		match = URL_RE.search(text or "")
		if not match:
			return None
		return match.group(1).rstrip(".,;:)]}")

	@staticmethod
	def _trim_search_result(result: dict[str, Any]) -> dict[str, Any]:
		trimmed = dict(result)
		raw_results = result.get("results", [])
		results = []
		if isinstance(raw_results, list):
			for item in raw_results:
				if not isinstance(item, dict):
					continue
				results.append(
					{
						"title": str(item.get("title") or "").strip(),
						"url": str(item.get("url") or "").strip(),
						"content": WebResearchAgent._trim_text(
							str(item.get("content") or ""),
							MAX_SEARCH_SNIPPET_CHARS,
						),
					}
				)
		trimmed["results"] = results
		trimmed["result_count"] = len(results)
		return trimmed

	@staticmethod
	def _trim_fetch_result(result: dict[str, Any]) -> dict[str, Any]:
		trimmed = dict(result)
		trimmed["content"] = WebResearchAgent._trim_text(
			str(result.get("content") or ""),
			MAX_FETCH_CONTENT_CHARS,
		)
		links = result.get("links", [])
		trimmed["links"] = links[:20] if isinstance(links, list) else []
		return trimmed

	@staticmethod
	def _trim_text(value: str, max_chars: int) -> str:
		text = value.strip()
		if len(text) <= max_chars:
			return text
		return text[: max_chars - 1].rstrip() + "…"

	@staticmethod
	def _summary(mode: str, analysis_payload: dict[str, Any]) -> str:
		if mode == "fetch":
			fetch = analysis_payload.get("fetch", {})
			if isinstance(fetch, dict) and fetch.get("status") == "ok":
				return f"web_fetch_ok title={fetch.get('title') or 'untitled'}"
			reason = fetch.get("reason") if isinstance(fetch, dict) else "unknown"
			return f"web_fetch_unavailable reason={reason}"
		search = analysis_payload.get("search", {})
		if isinstance(search, dict) and search.get("status") == "ok":
			return f"web_search_ok results={search.get('result_count', 0)}"
		reason = search.get("reason") if isinstance(search, dict) else "unknown"
		return f"web_search_unavailable reason={reason}"

	@staticmethod
	def _log_data(mode: str, analysis_payload: dict[str, Any]) -> dict[str, Any]:
		if mode == "fetch":
			fetch = analysis_payload.get("fetch", {})
			if not isinstance(fetch, dict):
				return {"status": "unknown"}
			return {
				"status": fetch.get("status"),
				"reason": fetch.get("reason") or "ok",
				"url": fetch.get("url") or analysis_payload.get("requested_url"),
			}
		search = analysis_payload.get("search", {})
		if not isinstance(search, dict):
			return {"status": "unknown"}
		return {
			"status": search.get("status"),
			"reason": search.get("reason") or "ok",
			"query": analysis_payload.get("query"),
			"results": search.get("result_count", 0),
			"top_fetch": (
				analysis_payload.get("top_fetch", {}).get("status")
				if isinstance(analysis_payload.get("top_fetch"), dict)
				else None
			),
		}
