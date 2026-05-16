"""Tiny TTL cache used by free-tier web-search integrations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TTLCache:
	ttl_seconds: int
	_values: dict[str, tuple[float, Any]] = field(default_factory=dict)

	def get(self, key: str) -> Any | None:
		if self.ttl_seconds <= 0:
			return None
		item = self._values.get(key)
		if item is None:
			return None
		expires_at, value = item
		if expires_at <= time.time():
			self._values.pop(key, None)
			return None
		return value

	def set(self, key: str, value: Any) -> None:
		if self.ttl_seconds <= 0:
			return
		self._values[key] = (time.time() + self.ttl_seconds, value)
