"""DuckDuckGo-backed web search client.

DuckDuckGo does not provide a public API-key based web search API for this
use case. This client uses DuckDuckGo's public HTML search endpoint with
bounded timeouts and small parsed result payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

DUCKDUCKGO_HTML_ENDPOINT = "https://html.duckduckgo.com/html/"
DEFAULT_USER_AGENT = (
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
	"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass(slots=True)
class DuckDuckGoSearchService:
	"""Small sync client for DuckDuckGo search and direct page fetch."""

	enabled: bool = True
	default_max_results: int = 5
	search_timeout_seconds: float = 10.0
	fetch_timeout_seconds: float = 10.0
	region: str = "wt-wt"
	search_endpoint: str = DUCKDUCKGO_HTML_ENDPOINT

	@property
	def available(self) -> bool:
		return self.enabled

	@property
	def unavailable_reason(self) -> str | None:
		return None if self.enabled else "web_search_disabled"

	def search(self, query: str, max_results: int | None = None) -> dict[str, Any]:
		query = " ".join((query or "").split())
		if not query:
			return self._unavailable_payload("empty_query", query=query)
		if not self.available:
			return self._unavailable_payload(
				self.unavailable_reason or "web_search_unavailable",
				query=query,
			)

		result_limit = self._clamp_max_results(max_results)
		try:
			with httpx.Client(
				timeout=self.search_timeout_seconds,
				follow_redirects=True,
				headers=self._headers(),
			) as client:
				response = client.get(
					self.search_endpoint,
					params={
						"q": query,
						"kl": self.region,
					},
				)
				response.raise_for_status()
		except httpx.TimeoutException:
			return self._error_payload("timeout", query=query)
		except httpx.HTTPStatusError as exc:
			return self._error_payload(
				"http_status_error",
				query=query,
				status_code=exc.response.status_code,
			)
		except httpx.HTTPError as exc:
			return self._error_payload(
				"http_error",
				query=query,
				error_type=type(exc).__name__,
			)

		results = DuckDuckGoHTMLParser.parse(response.text)[:result_limit]
		return {
			"available": True,
			"status": "ok",
			"provider": "duckduckgo",
			"query": query,
			"max_results": result_limit,
			"result_count": len(results),
			"results": results,
		}

	def fetch(self, url: str) -> dict[str, Any]:
		url = self._normalise_url(url)
		if not url:
			return self._unavailable_payload("empty_url")
		if not self.available:
			return self._unavailable_payload(
				self.unavailable_reason or "web_fetch_unavailable",
				url=url,
			)

		try:
			with httpx.Client(
				timeout=self.fetch_timeout_seconds,
				follow_redirects=True,
				headers=self._headers(),
			) as client:
				response = client.get(url)
				response.raise_for_status()
		except httpx.TimeoutException:
			return self._error_payload("timeout", url=url)
		except httpx.HTTPStatusError as exc:
			return self._error_payload(
				"http_status_error",
				url=url,
				status_code=exc.response.status_code,
			)
		except httpx.HTTPError as exc:
			return self._error_payload(
				"http_error",
				url=url,
				error_type=type(exc).__name__,
			)

		parser = PageTextParser()
		parser.feed(response.text)
		return {
			"available": True,
			"status": "ok",
			"provider": "duckduckgo",
			"url": str(response.url),
			"title": parser.title.strip(),
			"content": " ".join(parser.text_parts).strip(),
			"links": parser.links[:50],
		}

	@staticmethod
	def _headers() -> dict[str, str]:
		return {
			"User-Agent": DEFAULT_USER_AGENT,
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
			"Accept-Language": "vi,en-US;q=0.8,en;q=0.6",
		}

	def _clamp_max_results(self, max_results: int | None) -> int:
		value = max_results if max_results is not None else self.default_max_results
		try:
			number = int(value)
		except TypeError, ValueError:
			number = self.default_max_results
		return max(1, min(number, 10))

	@staticmethod
	def _normalise_url(url: str) -> str:
		cleaned = " ".join((url or "").split())
		if not cleaned:
			return ""
		if cleaned.startswith(("http://", "https://")):
			return cleaned
		return f"https://{cleaned}"

	@staticmethod
	def _unavailable_payload(reason: str, **extra: Any) -> dict[str, Any]:
		return {
			"available": False,
			"status": "unavailable",
			"provider": "duckduckgo",
			"reason": reason,
			"results": [],
			**extra,
		}

	@staticmethod
	def _error_payload(reason: str, **extra: Any) -> dict[str, Any]:
		return {
			"available": False,
			"status": "error",
			"provider": "duckduckgo",
			"reason": reason,
			"results": [],
			**extra,
		}


class DuckDuckGoHTMLParser(HTMLParser):
	"""Extract result title, URL, and snippet from DuckDuckGo HTML."""

	def __init__(self) -> None:
		super().__init__(convert_charrefs=True)
		self.results: list[dict[str, str]] = []
		self._current: dict[str, str] | None = None
		self._capture_title = False
		self._capture_snippet = False
		self._title_parts: list[str] = []
		self._snippet_parts: list[str] = []

	@classmethod
	def parse(cls, html: str) -> list[dict[str, str]]:
		parser = cls()
		parser.feed(html)
		parser.close()
		return parser.results

	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		attr = dict(attrs)
		class_name = attr.get("class") or ""
		if tag == "a" and "result__a" in class_name:
			self._flush_current()
			self._current = {
				"title": "",
				"url": self._clean_duckduckgo_url(attr.get("href") or ""),
				"content": "",
			}
			self._capture_title = True
			self._title_parts = []
			return
		if (
			tag in {"a", "div"}
			and "result__snippet" in class_name
			and self._current is not None
		):
			self._capture_snippet = True
			self._snippet_parts = []

	def handle_endtag(self, tag: str) -> None:
		if tag == "a" and self._capture_title and self._current is not None:
			self._current["title"] = self._clean_text(" ".join(self._title_parts))
			self._capture_title = False
			return
		if self._capture_snippet and tag in {"a", "div"} and self._current is not None:
			self._current["content"] = self._clean_text(" ".join(self._snippet_parts))
			self._capture_snippet = False

	def handle_data(self, data: str) -> None:
		if self._capture_title:
			self._title_parts.append(data)
		if self._capture_snippet:
			self._snippet_parts.append(data)

	def close(self) -> None:
		self._flush_current()
		super().close()

	def _flush_current(self) -> None:
		if not self._current:
			return
		if self._current.get("title") or self._current.get("url"):
			self.results.append(self._current)
		self._current = None
		self._capture_title = False
		self._capture_snippet = False

	@staticmethod
	def _clean_text(value: str) -> str:
		return " ".join(unescape(value or "").split())

	@staticmethod
	def _clean_duckduckgo_url(value: str) -> str:
		raw = unescape(value or "").strip()
		if not raw:
			return ""
		parsed = urlparse(raw)
		if parsed.path.startswith("/l/"):
			target = parse_qs(parsed.query).get("uddg", [""])[0]
			return unquote(target)
		return raw


class PageTextParser(HTMLParser):
	"""Very small HTML-to-text extractor for fetched pages."""

	def __init__(self) -> None:
		super().__init__(convert_charrefs=True)
		self.title = ""
		self.links: list[str] = []
		self.text_parts: list[str] = []
		self._capture_title = False
		self._skip_depth = 0

	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		if tag in {"script", "style", "noscript", "svg"}:
			self._skip_depth += 1
			return
		if tag == "title":
			self._capture_title = True
		if tag == "a":
			href = dict(attrs).get("href")
			if href:
				self.links.append(href)

	def handle_endtag(self, tag: str) -> None:
		if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
			self._skip_depth -= 1
			return
		if tag == "title":
			self._capture_title = False

	def handle_data(self, data: str) -> None:
		if self._skip_depth:
			return
		text = " ".join((data or "").split())
		if not text:
			return
		if self._capture_title:
			self.title = f"{self.title} {text}".strip()
		elif len(text) > 1:
			self.text_parts.append(text)
