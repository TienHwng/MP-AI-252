"""OpenStreetMap Nominatim places client."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import httpx
from core.logger import log_agent

from web_search.cache import TTLCache

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_USER_AGENT = "HERA-IoT/1.0 (local assistant; contact: local)"


@dataclass(slots=True)
class NominatimPlacesService:
	enabled: bool = True
	timeout_seconds: float = 8.0
	cache_ttl_seconds: int = 86400
	default_location: str = "Ho Chi Minh City, Vietnam"
	user_agent: str = DEFAULT_USER_AGENT
	cache: TTLCache = field(init=False)

	def __post_init__(self) -> None:
		self.cache = TTLCache(self.cache_ttl_seconds)

	@property
	def available(self) -> bool:
		return self.enabled

	@property
	def unavailable_reason(self) -> str | None:
		return None if self.enabled else "places_search_disabled"

	def search(
		self,
		query: str,
		location: str | None = None,
		category: str | None = None,
		max_results: int = 5,
	) -> dict[str, Any]:
		query = " ".join((query or category or "").split())
		location = " ".join((location or self.default_location).split())
		limit = max(1, min(int(max_results or 5), 10))
		if not query:
			return self._unavailable_payload("empty_query")
		if not self.available:
			return self._unavailable_payload(
				self.unavailable_reason or "places_unavailable"
			)

		cache_key = f"{query.lower()}:{location.lower()}:{category}:{limit}"
		cached = self.cache.get(cache_key)
		if cached is not None:
			return cached

		origin = self._geocode(location)
		search_query = f"{query} near {location}" if location else query
		try:
			raw_places = self._nominatim(search_query, limit)
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

		places = [
			self._place(item, origin) for item in raw_places if isinstance(item, dict)
		]
		result = {
			"available": True,
			"status": "ok",
			"provider": "nominatim",
			"query": query,
			"location": location,
			"category": category,
			"data": places,
			"results": [
				{
					"title": place["name"],
					"url": place["website"] or "https://www.openstreetmap.org/",
					"content": place["address"],
				}
				for place in places
			],
			"result_count": len(places),
		}
		self.cache.set(cache_key, result)
		log_agent(
			"Places API call complete",
			data={"status": "ok", "results": len(places)},
		)
		return result

	def _nominatim(self, query: str, limit: int) -> list[dict[str, Any]]:
		with httpx.Client(
			timeout=self.timeout_seconds, headers={"User-Agent": self.user_agent}
		) as client:
			response = client.get(
				NOMINATIM_SEARCH_URL,
				params={
					"q": query,
					"format": "jsonv2",
					"addressdetails": 1,
					"extratags": 1,
					"limit": limit,
				},
			)
			response.raise_for_status()
			payload = response.json()
		return payload if isinstance(payload, list) else []

	def _geocode(self, location: str) -> tuple[float, float] | None:
		if not location:
			return None
		cache_key = f"geocode:{location.lower()}"
		cached = self.cache.get(cache_key)
		if cached is not None:
			return cached
		try:
			items = self._nominatim(location, 1)
		except Exception:
			return None
		if not items:
			return None
		try:
			coords = (float(items[0]["lat"]), float(items[0]["lon"]))
		except KeyError, TypeError, ValueError:
			return None
		self.cache.set(cache_key, coords)
		return coords

	def _place(
		self,
		item: dict[str, Any],
		origin: tuple[float, float] | None,
	) -> dict[str, Any]:
		lat = float(item.get("lat", 0))
		lon = float(item.get("lon", 0))
		extratags = (
			item.get("extratags") if isinstance(item.get("extratags"), dict) else {}
		)
		return {
			"name": str(item.get("name") or item.get("display_name") or "").split(",")[
				0
			],
			"address": str(item.get("display_name") or "").strip(),
			"type": str(item.get("type") or item.get("class") or "").strip(),
			"distance": round(self._distance_km(origin, (lat, lon)), 2)
			if origin
			else None,
			"coordinates": {"lat": lat, "lon": lon},
			"website": str(extratags.get("website") or "").strip(),
		}

	@staticmethod
	def _distance_km(
		start: tuple[float, float] | None,
		end: tuple[float, float],
	) -> float:
		if start is None:
			return 0.0
		lat1, lon1 = (math.radians(value) for value in start)
		lat2, lon2 = (math.radians(value) for value in end)
		dlat = lat2 - lat1
		dlon = lon2 - lon1
		a = (
			math.sin(dlat / 2) ** 2
			+ math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
		)
		return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

	@staticmethod
	def _unavailable_payload(reason: str, **extra: Any) -> dict[str, Any]:
		return {
			"available": False,
			"status": "unavailable",
			"provider": "nominatim",
			"reason": reason,
			"results": [],
			**extra,
		}

	@staticmethod
	def _error_payload(reason: str, **extra: Any) -> dict[str, Any]:
		log_agent(
			"Places API call failed", data={"reason": reason, "provider": "nominatim"}
		)
		return {
			"available": False,
			"status": "error",
			"provider": "nominatim",
			"reason": reason,
			"results": [],
			**extra,
		}
