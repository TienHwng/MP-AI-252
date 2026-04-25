"""Free-tier price lookup client.

Supports common crypto assets through CoinGecko and fiat exchange rates through
Frankfurter. Unsupported assets return unavailable so the agent can fallback to
generic web search.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from core.logger import log_agent

from web_search.cache import TTLCache

COINGECKO_SIMPLE_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"
FRANKFURTER_LATEST_URL = "https://api.frankfurter.app/latest"

CRYPTO_IDS = {
	"btc": "bitcoin",
	"bitcoin": "bitcoin",
	"eth": "ethereum",
	"ethereum": "ethereum",
	"bnb": "binancecoin",
	"sol": "solana",
	"solana": "solana",
	"doge": "dogecoin",
	"dogecoin": "dogecoin",
}
CURRENCIES = {"usd", "eur", "vnd", "jpy", "gbp", "aud", "cad", "sgd", "krw", "cny"}


@dataclass(slots=True)
class PriceSearchService:
	enabled: bool = True
	timeout_seconds: float = 8.0
	cache_ttl_seconds: int = 300
	default_currency: str = "usd"
	cache: TTLCache = field(init=False)

	def __post_init__(self) -> None:
		self.cache = TTLCache(self.cache_ttl_seconds)

	@property
	def available(self) -> bool:
		return self.enabled

	@property
	def unavailable_reason(self) -> str | None:
		return None if self.enabled else "price_search_disabled"

	def search(self, query: str) -> dict[str, Any]:
		query = " ".join((query or "").split())
		if not query:
			return self._unavailable_payload("empty_query")
		if not self.available:
			return self._unavailable_payload(
				self.unavailable_reason or "price_unavailable"
			)

		cache_key = query.lower()
		cached = self.cache.get(cache_key)
		if cached is not None:
			return cached

		crypto_id = self._extract_crypto_id(query)
		if crypto_id:
			result = self._crypto_price(
				query, crypto_id, self._extract_quote_currency(query)
			)
		else:
			currency_pair = self._extract_currency_pair(query)
			result = (
				self._currency_rate(query, *currency_pair)
				if currency_pair is not None
				else self._unavailable_payload("unsupported_price_query", query=query)
			)
		self.cache.set(cache_key, result)
		return result

	def _crypto_price(self, query: str, asset_id: str, currency: str) -> dict[str, Any]:
		try:
			with httpx.Client(timeout=self.timeout_seconds) as client:
				response = client.get(
					COINGECKO_SIMPLE_PRICE_URL,
					params={
						"ids": asset_id,
						"vs_currencies": currency,
						"include_24hr_change": "true",
					},
				)
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

		item = payload.get(asset_id, {}) if isinstance(payload, dict) else {}
		price = item.get(currency)
		if price is None:
			return self._error_payload("price_not_found", query=query)
		change = item.get(f"{currency}_24h_change")
		data = {
			"asset": asset_id,
			"currency": currency.upper(),
			"current_price": price,
			"change_24h": round(float(change), 2) if change is not None else None,
			"source": "CoinGecko",
		}
		result = self._ok_payload(query, data, "coingecko")
		log_agent(
			"Price API call complete", data={"provider": "coingecko", "asset": asset_id}
		)
		return result

	def _currency_rate(self, query: str, base: str, quote: str) -> dict[str, Any]:
		try:
			with httpx.Client(timeout=self.timeout_seconds) as client:
				response = client.get(
					FRANKFURTER_LATEST_URL,
					params={"from": base.upper(), "to": quote.upper()},
				)
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

		rate = (payload.get("rates") or {}).get(quote.upper())
		if rate is None:
			return self._error_payload("rate_not_found", query=query)
		data = {
			"asset": f"{base.upper()}/{quote.upper()}",
			"currency": quote.upper(),
			"current_price": rate,
			"change_24h": None,
			"source": "Frankfurter",
			"date": payload.get("date"),
		}
		result = self._ok_payload(query, data, "frankfurter")
		log_agent(
			"Price API call complete",
			data={"provider": "frankfurter", "asset": data["asset"]},
		)
		return result

	def _ok_payload(
		self, query: str, data: dict[str, Any], provider: str
	) -> dict[str, Any]:
		change = data.get("change_24h")
		change_text = "" if change is None else f"; 24h change {change}%"
		return {
			"available": True,
			"status": "ok",
			"provider": provider,
			"query": query,
			"data": data,
			"results": [
				{
					"title": f"{data['asset']} price",
					"url": "https://www.coingecko.com/"
					if provider == "coingecko"
					else "https://www.frankfurter.app/",
					"content": f"{data['asset']} = {data['current_price']} {data['currency']}{change_text}",
				}
			],
			"result_count": 1,
		}

	@staticmethod
	def _extract_crypto_id(query: str) -> str | None:
		lower = query.lower()
		for marker, asset_id in CRYPTO_IDS.items():
			if re.search(rf"\b{re.escape(marker)}\b", lower):
				return asset_id
		return None

	def _extract_quote_currency(self, query: str) -> str:
		lower = query.lower()
		for currency in CURRENCIES:
			if re.search(rf"\b{currency}\b", lower):
				return currency
		if "vnd" in lower or "việt nam" in lower or "viet nam" in lower:
			return "vnd"
		return self.default_currency.lower()

	@staticmethod
	def _extract_currency_pair(query: str) -> tuple[str, str] | None:
		lower = query.lower()
		match = re.search(r"\b([a-z]{3})\s*/\s*([a-z]{3})\b", lower)
		if match and match.group(1) in CURRENCIES and match.group(2) in CURRENCIES:
			return match.group(1), match.group(2)
		codes = [code for code in CURRENCIES if re.search(rf"\b{code}\b", lower)]
		if len(codes) >= 2:
			return codes[0], codes[1]
		return None

	@staticmethod
	def _unavailable_payload(reason: str, **extra: Any) -> dict[str, Any]:
		return {
			"available": False,
			"status": "unavailable",
			"provider": "price",
			"reason": reason,
			"results": [],
			**extra,
		}

	@staticmethod
	def _error_payload(reason: str, **extra: Any) -> dict[str, Any]:
		log_agent("Price API call failed", data={"reason": reason})
		return {
			"available": False,
			"status": "error",
			"provider": "price",
			"reason": reason,
			"results": [],
			**extra,
		}
