"""Enhanced DuckDuckGo client using Playwright for better content extraction."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from web_search.duckduckgo_client import DuckDuckGoSearchService

try:
	from playwright.async_api import async_playwright, Browser

	HAS_PLAYWRIGHT = True
except ImportError:
	HAS_PLAYWRIGHT = False


@dataclass(slots=True)
class PlaywrightFetcher:
	"""Async content fetcher using Playwright for JS-heavy sites."""

	enabled: bool = HAS_PLAYWRIGHT
	headless: bool = True
	timeout_ms: int = 15000
	wait_time_ms: int = 1000
	user_agent: str = (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
		"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
	)

	async def fetch(self, url: str) -> dict[str, Any]:
		"""Fetch URL using Playwright browser and extract clean content."""
		if not self.enabled:
			return self._error_payload("playwright_disabled", url=url)

		if not url or not isinstance(url, str):
			return self._error_payload("invalid_url", url=str(url or ""))

		try:
			async with async_playwright() as p:
				browser = await p.chromium.launch(headless=self.headless)
				page = await browser.new_page(user_agent=self.user_agent)

				try:
					# Navigate with timeout
					await page.goto(
						url,
						wait_until="networkidle",
						timeout=self.timeout_ms,
					)

					# Wait for JS to settle
					await asyncio.sleep(self.wait_time_ms / 1000)

					# Extract content
					title = await page.title()
					content = await page.inner_text("body")

					# Clean up whitespace
					content = "\n".join(
						line.strip() for line in content.split("\n") if line.strip()
					)

					result = {
						"available": True,
						"status": "ok",
						"provider": "playwright",
						"url": str(page.url),
						"title": title.strip(),
						"content": content,
					}

					return result

				except asyncio.TimeoutError:
					return self._error_payload("timeout", url=url)
				except Exception as e:
					return self._error_payload(
						"browser_error",
						url=url,
						error=str(e),
					)
				finally:
					await browser.close()

		except Exception as e:
			return self._error_payload(
				"playwright_error",
				url=url,
				error=str(e),
			)

	@staticmethod
	def _error_payload(reason: str, **extra: Any) -> dict[str, Any]:
		return {
			"available": False,
			"status": "error",
			"provider": "playwright",
			"reason": reason,
			"content": "",
			**extra,
		}


async def fetch_and_extract(url: str) -> dict[str, Any]:
	"""Async helper to fetch URL and return LLM-ready content."""
	fetcher = PlaywrightFetcher()

	# Fetch with Playwright
	result = await fetcher.fetch(url)

	# Format for LLM
	if result.get("status") == "ok":
		return {
			"source": result.get("url"),
			"title": result.get("title"),
			"content": result.get("content"),
			"status": "success",
		}
	else:
		return {
			"source": url,
			"title": "Error",
			"content": f"Failed to fetch: {result.get('reason')}",
			"status": "error",
		}


def search_and_fetch(query: str, use_playwright: bool = True) -> dict[str, Any]:
	"""Search with DuckDuckGo, then fetch top result with Playwright (async wrapper).

	Args:
		query: Search query
		use_playwright: If True, use Playwright for fetching; else use httpx

	Returns:
		dict with search results and top result content
	"""

	# Search
	service = DuckDuckGoSearchService()
	search_result = service.search(query, max_results=5)

	if not search_result.get("results"):
		return {
			"query": query,
			"search_status": "no_results",
			"results": [],
		}

	# Get top URL
	top_url = search_result["results"][0].get("url")

	if use_playwright and HAS_PLAYWRIGHT:
		# Async fetch with Playwright
		fetch_result = asyncio.run(fetch_and_extract(top_url))
	else:
		# Sync fetch with httpx
		fetch_result = service.fetch(top_url)
		fetch_result = {
			"source": fetch_result.get("url"),
			"title": fetch_result.get("title"),
			"content": fetch_result.get("content"),
			"status": fetch_result.get("status"),
		}

	return {
		"query": query,
		"search_status": "ok",
		"results_count": len(search_result.get("results", [])),
		"results": search_result.get("results"),
		"top_result": fetch_result,
	}
