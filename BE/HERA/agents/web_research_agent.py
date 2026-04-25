"""Web research agent backed by the configured search provider."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from core.logger import log_agent
from core.message import AgentResponse, UserMessage
from schemas import SpecialistReport

from agents.base import AgentBase

URL_RE = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.IGNORECASE)
MAX_SEARCH_SNIPPET_CHARS = 1200
MAX_FETCH_CONTENT_CHARS = 6000


class WebResearchAgent(AgentBase):
	"""Runs bounded web search/fetch work and returns structured evidence."""

	def __init__(
		self,
		search_service,
		max_results: int = 5,
	) -> None:
		self.search_service = search_service
		self.max_results = max_results

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
		query = self._query_from_route_plan(route_plan, message.text)
		url = self._extract_url(message.text)

		if url:
			result = await asyncio.to_thread(self.search_service.fetch, url)
			mode = "fetch"
			analysis_payload = {
				"mode": mode,
				"requested_url": url,
				"fetch": self._trim_fetch_result(result),
			}
		else:
			result = await asyncio.to_thread(
				self.search_service.search,
				query,
				self.max_results,
			)
			mode = "search"
			analysis_payload = {
				"mode": mode,
				"query": query,
				"search": self._trim_search_result(result),
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

	@staticmethod
	def _query_from_route_plan(route_plan: dict, fallback: str) -> str:
		query = route_plan.get("web_query")
		if isinstance(query, str) and query.strip():
			return " ".join(query.split())
		return " ".join((fallback or "").split())

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
			"results": search.get("result_count", 0),
		}
