"""OpenWeatherMap forecast client."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import httpx
from core.logger import log_agent

from web_search.cache import TTLCache

OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


@dataclass(slots=True)
class OpenWeatherMapService:
	api_key: str | None = None
	enabled: bool = True
	timeout_seconds: float = 8.0
	cache_ttl_seconds: int = 3600
	default_location: str = "Ho Chi Minh City, Vietnam"
	cache: TTLCache = field(init=False)

	def __post_init__(self) -> None:
		self.cache = TTLCache(self.cache_ttl_seconds)

	@property
	def available(self) -> bool:
		return self.enabled and bool((self.api_key or "").strip())

	@property
	def unavailable_reason(self) -> str | None:
		if not self.enabled:
			return "weather_search_disabled"
		if not (self.api_key or "").strip():
			return "missing_openweathermap_api_key"
		return None

	def forecast(
		self, location: str | None = None, days_ahead: int = 0
	) -> dict[str, Any]:
		location = " ".join((location or self.default_location).split())
		days_ahead = max(0, min(int(days_ahead or 0), 5))
		if not self.available:
			return self._unavailable_payload(
				self.unavailable_reason or "weather_unavailable"
			)

		cache_key = f"{location.lower()}:{days_ahead}"
		cached = self.cache.get(cache_key)
		if cached is not None:
			return cached

		try:
			with httpx.Client(timeout=self.timeout_seconds) as client:
				response = client.get(
					OPENWEATHER_FORECAST_URL,
					params={
						"q": location,
						"appid": self.api_key,
						"units": "metric",
						"lang": "vi",
					},
				)
				response.raise_for_status()
				payload = response.json()
		except httpx.TimeoutException:
			return self._error_payload("timeout", location=location)
		except httpx.HTTPStatusError as exc:
			return self._error_payload(
				"http_status_error",
				location=location,
				status_code=exc.response.status_code,
			)
		except (httpx.HTTPError, ValueError) as exc:
			return self._error_payload(
				"http_error",
				location=location,
				error_type=type(exc).__name__,
			)

		result = self._parse_forecast(payload, location, days_ahead)
		self.cache.set(cache_key, result)
		log_agent(
			"Weather API call complete",
			data={"status": result.get("status"), "location": location},
		)
		return result

	def _parse_forecast(
		self,
		payload: dict[str, Any],
		location: str,
		days_ahead: int,
	) -> dict[str, Any]:
		target_date = (datetime.now().astimezone() + timedelta(days=days_ahead)).date()
		items = [
			item
			for item in payload.get("list", [])
			if isinstance(item, dict)
			and datetime.fromtimestamp(int(item.get("dt", 0))).date() == target_date
		]
		if not items:
			items = [
				item for item in payload.get("list", []) if isinstance(item, dict)
			][:1]
		if not items:
			return self._error_payload("empty_forecast", location=location)

		temps_min = [float(item.get("main", {}).get("temp_min")) for item in items]
		temps_max = [float(item.get("main", {}).get("temp_max")) for item in items]
		humidity = [float(item.get("main", {}).get("humidity")) for item in items]
		wind = [float(item.get("wind", {}).get("speed", 0)) for item in items]
		pop = [float(item.get("pop", 0)) for item in items]
		weather = items[0].get("weather") or [{}]
		condition = str(weather[0].get("description") or weather[0].get("main") or "")
		city = payload.get("city", {}) if isinstance(payload.get("city"), dict) else {}
		resolved_location = city.get("name") or location
		country = city.get("country")
		if country:
			resolved_location = f"{resolved_location}, {country}"

		data = {
			"location": resolved_location,
			"date": target_date.isoformat(),
			"days_ahead": days_ahead,
			"temp_min": round(min(temps_min), 1),
			"temp_max": round(max(temps_max), 1),
			"condition": condition,
			"rain_probability": round(max(pop), 2),
			"humidity": round(sum(humidity) / len(humidity), 1),
			"wind_speed": round(sum(wind) / len(wind), 1),
		}
		return {
			"available": True,
			"status": "ok",
			"provider": "openweathermap",
			"query": location,
			"data": data,
			"results": [self._result_from_data(data)],
			"result_count": 1,
		}

	@staticmethod
	def _result_from_data(data: dict[str, Any]) -> dict[str, str]:
		return {
			"title": f"Weather forecast for {data['location']} on {data['date']}",
			"url": "https://openweathermap.org/",
			"content": (
				f"{data['condition']}; {data['temp_min']}–{data['temp_max']}°C; "
				f"rain probability {int(data['rain_probability'] * 100)}%; "
				f"humidity {data['humidity']}%; wind {data['wind_speed']} m/s"
			),
		}

	@staticmethod
	def _unavailable_payload(reason: str, **extra: Any) -> dict[str, Any]:
		return {
			"available": False,
			"status": "unavailable",
			"provider": "openweathermap",
			"reason": reason,
			"results": [],
			**extra,
		}

	@staticmethod
	def _error_payload(reason: str, **extra: Any) -> dict[str, Any]:
		log_agent(
			"Weather API call failed",
			data={"reason": reason, "provider": "openweathermap"},
		)
		return {
			"available": False,
			"status": "error",
			"provider": "openweathermap",
			"reason": reason,
			"results": [],
			**extra,
		}
