"""Optional Google Calendar client.

The service is intentionally unavailable unless explicitly enabled and local
Google credentials are present. This keeps HERA's default web-search pipeline
free of mandatory user auth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from core.logger import log_agent

from web_search.cache import TTLCache


@dataclass(slots=True)
class GoogleCalendarService:
	credentials_path: str | None = None
	enabled: bool = False
	timeout_seconds: float = 8.0
	cache_ttl_seconds: int = 1800
	calendar_id: str = "primary"
	cache: TTLCache = field(init=False)

	def __post_init__(self) -> None:
		self.cache = TTLCache(self.cache_ttl_seconds)

	@property
	def available(self) -> bool:
		return (
			self.enabled
			and bool(self.credentials_path)
			and Path(self.credentials_path).exists()
		)

	@property
	def unavailable_reason(self) -> str | None:
		if not self.enabled:
			return "calendar_search_disabled"
		if not self.credentials_path:
			return "missing_google_calendar_credentials_path"
		if not Path(self.credentials_path).exists():
			return "google_calendar_credentials_not_found"
		return None

	def events(self, user_id: str | None = None, days_ahead: int = 0) -> dict[str, Any]:
		days_ahead = max(0, min(int(days_ahead or 0), 30))
		if not self.available:
			return self._unavailable_payload(
				self.unavailable_reason or "calendar_unavailable",
			)
		cache_key = f"{user_id or 'default'}:{days_ahead}:{self.calendar_id}"
		cached = self.cache.get(cache_key)
		if cached is not None:
			return cached

		try:
			raw_events = self._read_google_events(days_ahead)
		except ImportError:
			return self._unavailable_payload("google_calendar_dependencies_missing")
		except Exception as exc:
			return self._error_payload("calendar_error", error_type=type(exc).__name__)

		events = [self._event(item) for item in raw_events if isinstance(item, dict)]
		result = {
			"available": True,
			"status": "ok",
			"provider": "google_calendar",
			"user_id": user_id,
			"days_ahead": days_ahead,
			"data": events,
			"results": [
				{
					"title": item["title"],
					"url": "https://calendar.google.com/",
					"content": f"{item['start_time']} - {item['end_time']} {item['location']}".strip(),
				}
				for item in events
			],
			"result_count": len(events),
		}
		self.cache.set(cache_key, result)
		log_agent(
			"Calendar API call complete",
			data={"status": "ok", "events": len(events)},
		)
		return result

	def _read_google_events(self, days_ahead: int) -> list[dict[str, Any]]:
		from google.oauth2.credentials import Credentials
		from googleapiclient.discovery import build

		creds = Credentials.from_authorized_user_file(
			str(self.credentials_path),
			["https://www.googleapis.com/auth/calendar.readonly"],
		)
		service = build("calendar", "v3", credentials=creds, cache_discovery=False)
		start = datetime.now(UTC)
		end = start + timedelta(days=max(1, days_ahead + 1))
		response = (
			service.events()
			.list(
				calendarId=self.calendar_id,
				timeMin=start.isoformat(),
				timeMax=end.isoformat(),
				singleEvents=True,
				orderBy="startTime",
				maxResults=20,
			)
			.execute()
		)
		return response.get("items", [])

	@staticmethod
	def _event(item: dict[str, Any]) -> dict[str, Any]:
		start = item.get("start", {}) if isinstance(item.get("start"), dict) else {}
		end = item.get("end", {}) if isinstance(item.get("end"), dict) else {}
		attendees = item.get("attendees", [])
		return {
			"title": str(item.get("summary") or "Untitled event").strip(),
			"start_time": str(start.get("dateTime") or start.get("date") or "").strip(),
			"end_time": str(end.get("dateTime") or end.get("date") or "").strip(),
			"location": str(item.get("location") or "").strip(),
			"attendees": [
				str(attendee.get("email") or "").strip()
				for attendee in attendees
				if isinstance(attendee, dict) and attendee.get("email")
			],
		}

	@staticmethod
	def _unavailable_payload(reason: str, **extra: Any) -> dict[str, Any]:
		return {
			"available": False,
			"status": "unavailable",
			"provider": "google_calendar",
			"reason": reason,
			"results": [],
			**extra,
		}

	@staticmethod
	def _error_payload(reason: str, **extra: Any) -> dict[str, Any]:
		log_agent(
			"Calendar API call failed",
			data={"reason": reason, "provider": "google_calendar"},
		)
		return {
			"available": False,
			"status": "error",
			"provider": "google_calendar",
			"reason": reason,
			"results": [],
			**extra,
		}
