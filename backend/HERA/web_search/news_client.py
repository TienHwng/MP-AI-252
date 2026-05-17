"""NewsAPI client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
from core.logger import log_agent

from web_search.cache import TTLCache

NEWSAPI_EVERYTHING_URL = "https://newsapi.org/v2/everything"
NEWSAPI_TOP_HEADLINES_URL = "https://newsapi.org/v2/top-headlines"

# Trusted Vietnamese news sources
TRUSTED_VN_DOMAINS = {
	"vnexpress.net",
	"dantri.com.vn",
	"tuoitre.vn",
	"thanhnien.vn",
	"vietnamnet.vn",
}


@dataclass(slots=True)
class NewsAPIService:
	api_key: str | None = None
	enabled: bool = True
	timeout_seconds: float = 8.0
	cache_ttl_seconds: int = 1800
	default_country: str = "vn"
	cache: TTLCache = field(init=False)

	def __post_init__(self) -> None:
		self.cache = TTLCache(self.cache_ttl_seconds)

	@property
	def available(self) -> bool:
		return self.enabled and bool((self.api_key or "").strip())

	@property
	def unavailable_reason(self) -> str | None:
		if not self.enabled:
			return "news_search_disabled"
		if not (self.api_key or "").strip():
			return "missing_newsapi_api_key"
		return None

	def search(
		self,
		query: str,
		country: str | None = None,
		category: str | None = None,
		max_results: int = 5,
	) -> dict[str, Any]:
		query = " ".join((query or "").split())
		country = (country or self.default_country or "").lower()
		limit = max(1, min(int(max_results or 5), 10))
		if not self.available:
			return self._unavailable_payload(
				self.unavailable_reason or "news_unavailable"
			)
		cache_key = f"{query.lower()}:{country}:{category}:{limit}"
		cached = self.cache.get(cache_key)
		if cached is not None:
			return cached

		endpoint = NEWSAPI_EVERYTHING_URL if query else NEWSAPI_TOP_HEADLINES_URL
		params: dict[str, Any] = {"apiKey": self.api_key, "pageSize": limit}
		if query:
			params.update({"q": query, "sortBy": "publishedAt", "language": "vi"})
		else:
			params["country"] = country
		if category:
			params["category"] = category

		try:
			with httpx.Client(timeout=self.timeout_seconds) as client:
				response = client.get(endpoint, params=params)
				response.raise_for_status()
				payload = response.json()
		except httpx.TimeoutException:
			return self._error_payload("timeout", query=query)
		except httpx.HTTPStatusError as exc:
			return self._error_payload(
				"http_status_error",
				query=query,
				status_code=exc.response.status_code,
			)
		except (httpx.HTTPError, ValueError) as exc:
			return self._error_payload(
				"http_error",
				query=query,
				error_type=type(exc).__name__,
			)

		articles = [
			self._article(item)
			for item in payload.get("articles", [])
			if isinstance(item, dict) and self._is_trusted_source(item.get("url", ""))
		][:limit]
		result = {
			"available": True,
			"status": "ok",
			"provider": "newsapi",
			"query": query,
			"country": country,
			"category": category,
			"data": articles,
			"results": [
				{
					"title": item["title"],
					"url": item["url"],
					"content": item["description"],
				}
				for item in articles
			],
			"result_count": len(articles),
		}
		self.cache.set(cache_key, result)
		log_agent(
			"News API call complete",
			data={"status": result.get("status"), "results": len(articles)},
		)
		return result

	@staticmethod
	def _is_trusted_source(url: str) -> bool:
		"""Check if URL is from trusted Vietnamese news domain."""
		if not url:
			return False
		url_lower = url.lower()
		return any(domain in url_lower for domain in TRUSTED_VN_DOMAINS)

	@staticmethod
	def _article(item: dict[str, Any]) -> dict[str, Any]:
		return {
			"title": str(item.get("title") or "").strip(),
			"description": str(item.get("description") or "").strip(),
			"url": str(item.get("url") or "").strip(),
			"published_at": str(item.get("publishedAt") or "").strip(),
		}

	@staticmethod
	def _unavailable_payload(reason: str, **extra: Any) -> dict[str, Any]:
		return {
			"available": False,
			"status": "unavailable",
			"provider": "newsapi",
			"reason": reason,
			"results": [],
			**extra,
		}

	@staticmethod
	def _error_payload(reason: str, **extra: Any) -> dict[str, Any]:
		log_agent(
			"News API call failed", data={"reason": reason, "provider": "newsapi"}
		)
		return {
			"available": False,
			"status": "error",
			"provider": "newsapi",
			"reason": reason,
			"results": [],
			**extra,
		}
