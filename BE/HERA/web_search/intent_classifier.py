"""Structured search intent classifier for HERA web research."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

SEARCH_INTENTS = {"weather", "news", "generic"}


@dataclass(slots=True)
class SearchIntent:
	intent: str
	confidence: float
	reason: str
	parameters: dict[str, Any] = field(default_factory=dict)


class SearchIntentClassifier:
	"""Keyword-first classifier with an optional LLM fallback hook."""

	WEATHER = (
		"weather",
		"forecast",
		"rain",
		"temperature outside",
		"thời tiết",
		"thoi tiet",
		"dự báo",
		"du bao",
		"mưa",
		"mua",
		"nắng",
		"nang",
		"bão",
		"bao",
	)
	NEWS = (
		"news",
		"headline",
		"latest",
		"breaking",
		"tin tức",
		"tin tuc",
		"tin mới",
		"tin moi",
		"mới nhất",
		"moi nhat",
		"thời sự",
		"thoi su",
	)

	def __init__(
		self,
		default_location: str = "Ho Chi Minh City, Vietnam",
		llm_classifier: Callable[[str], SearchIntent | dict[str, Any] | None]
		| None = None,
	) -> None:
		self.default_location = default_location
		self.llm_classifier = llm_classifier

	def classify(self, query: str) -> SearchIntent:
		text = " ".join((query or "").split())
		lower = text.lower()
		for intent, keywords in (
			("weather", self.WEATHER),
			("news", self.NEWS),
		):
			matched = [keyword for keyword in keywords if keyword in lower]
			if matched:
				return SearchIntent(
					intent=intent,
					confidence=min(0.95, 0.75 + len(matched) * 0.05),
					reason=f"keyword:{matched[0]}",
					parameters=self._parameters(intent, text),
				)

		if self.llm_classifier is not None:
			try:
				result = self.llm_classifier(text)
			except Exception:
				result = None
			parsed = self._parse_llm_result(result)
			if parsed is not None:
				return parsed

		return SearchIntent(
			intent="generic",
			confidence=0.5,
			reason="no_specialized_keywords",
			parameters={"query": text},
		)

	def _parameters(self, intent: str, query: str) -> dict[str, Any]:
		if intent == "weather":
			return {
				"location": self._extract_location(query),
				"days_ahead": self._extract_days_ahead(query),
			}
		if intent == "news":
			return {"query": query, "country": self._extract_country(query)}
		return {"query": query}

	def _extract_location(self, query: str) -> str:
		cleaned = query
		for pattern in (
			r"\b(?:weather|forecast|rain)\b",
			r"\b(?:today|tomorrow|tonight)\b",
			r"\b(?:thời tiết|thoi tiet|dự báo|du bao|mưa|mua|hôm nay|hom nay|ngày mai|ngay mai|mai)\b",
		):
			cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
		cleaned = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", " ", cleaned)
		cleaned = " ".join(cleaned.split(" tại ", 1)[-1].split())
		if len(cleaned) >= 3 and not cleaned.endswith("?"):
			return cleaned.rstrip("?., ")
		return self.default_location

	@staticmethod
	def _extract_days_ahead(query: str) -> int:
		lower = query.lower()
		if any(
			marker in lower for marker in ("tomorrow", "ngày mai", "ngay mai", "mai")
		):
			return 1
		match = re.search(r"(\d{1,2})\s*(?:days?|ngày|ngay)", lower)
		if match:
			return max(0, min(int(match.group(1)), 14))
		date_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", query)
		if date_match:
			day, month, year = (int(part) for part in date_match.groups())
			if year < 100:
				year += 2000
			target = datetime(year, month, day).date()
			return max(0, (target - datetime.now().astimezone().date()).days)
		return 0

	@staticmethod
	def _extract_country(query: str) -> str | None:
		lower = query.lower()
		if any(marker in lower for marker in ("việt nam", "viet nam", "vietnam")):
			return "vn"
		if any(
			marker in lower for marker in ("us", "usa", "united states", "mỹ", "my")
		):
			return "us"
		return None

	@staticmethod
	def target_date(days_ahead: int) -> str:
		return (
			(datetime.now().astimezone() + timedelta(days=days_ahead))
			.date()
			.isoformat()
		)

	@staticmethod
	def _parse_llm_result(
		result: SearchIntent | dict[str, Any] | None,
	) -> SearchIntent | None:
		if isinstance(result, SearchIntent):
			return result if result.intent in SEARCH_INTENTS else None
		if not isinstance(result, dict):
			return None
		intent = str(result.get("intent") or "").lower()
		if intent not in SEARCH_INTENTS:
			return None
		return SearchIntent(
			intent=intent,
			confidence=float(result.get("confidence") or 0.6),
			reason=str(result.get("reason") or "llm_fallback"),
			parameters=dict(result.get("parameters") or {}),
		)
