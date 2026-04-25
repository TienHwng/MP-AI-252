"""MongoDB-backed telemetry history reader for runtime anomaly analysis."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Any

from memory.mongo_client import MongoMemoryClient
from pymongo.errors import PyMongoError


class TelemetryStore:
	"""Reads recent telemetry_points and computes lightweight runtime summaries."""

	def __init__(
		self,
		mongo: MongoMemoryClient,
		*,
		collection_name: str = "telemetry_points",
		device_id: str = "device_0001",
	) -> None:
		self.mongo = mongo
		self.collection_name = collection_name
		self.device_id = device_id

	def recent_summary(
		self,
		*,
		user_id: str | None,
		window_minutes: int,
		limit: int,
	) -> dict[str, Any]:
		collection = self.mongo.collection(self.collection_name)
		if collection is None:
			return {
				"available": False,
				"reason": "mongo_unavailable",
				"source": f"mongodb.{self.collection_name}",
			}

		cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
		base_filter: dict[str, Any] = {
			"metadata.device_id": self.device_id,
			"recorded_at": {"$gte": cutoff},
		}
		points, scope = self._find_recent_points(
			collection,
			base_filter,
			user_id=user_id,
			limit=limit,
		)
		if not points:
			return {
				"available": True,
				"reason": "no_recent_telemetry",
				"source": f"mongodb.{self.collection_name}",
				"scope": scope,
				"window_minutes": window_minutes,
				"point_limit": limit,
				"point_count": 0,
			}

		return self._summary_payload(
			points,
			scope=scope,
			limit=limit,
			window_key="window_minutes",
			window_value=window_minutes,
		)

	def recent_summary_seconds(
		self,
		*,
		user_id: str | None,
		window_seconds: int,
		limit: int,
	) -> dict[str, Any]:
		collection = self.mongo.collection(self.collection_name)
		if collection is None:
			return {
				"available": False,
				"reason": "mongo_unavailable",
				"source": f"mongodb.{self.collection_name}",
			}

		window_seconds = max(1, int(window_seconds))
		cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
		base_filter: dict[str, Any] = {
			"metadata.device_id": self.device_id,
			"recorded_at": {"$gte": cutoff},
		}
		points, scope = self._find_recent_points(
			collection,
			base_filter,
			user_id=user_id,
			limit=limit,
		)
		if not points:
			return {
				"available": True,
				"reason": "no_recent_telemetry",
				"source": f"mongodb.{self.collection_name}",
				"scope": scope,
				"window_seconds": window_seconds,
				"point_limit": limit,
				"point_count": 0,
			}

		return self._summary_payload(
			points,
			scope=scope,
			limit=limit,
			window_key="window_seconds",
			window_value=window_seconds,
		)

	def _summary_payload(
		self,
		points: list[dict[str, Any]],
		*,
		scope: str,
		limit: int,
		window_key: str,
		window_value: int,
	) -> dict[str, Any]:
		return {
			"available": True,
			"reason": "ok",
			"source": f"mongodb.{self.collection_name}",
			"scope": scope,
			window_key: window_value,
			"point_limit": limit,
			"point_count": len(points),
			"first_recorded_at": self._iso(points[0].get("recorded_at")),
			"last_recorded_at": self._iso(points[-1].get("recorded_at")),
			"temperature_c": self._numeric_summary(points, "temperature"),
			"humidity_percent": self._numeric_summary(points, "humidity"),
			"light": self._numeric_summary(points, "light"),
			"anomaly_score": self._numeric_summary(points, "anomaly"),
			"anomaly_events": self._anomaly_events(points),
			"stream": self._stream_summary(points),
		}

	def _find_recent_points(
		self,
		collection,
		base_filter: dict[str, Any],
		*,
		user_id: str | None,
		limit: int,
	) -> tuple[list[dict[str, Any]], str]:
		if user_id:
			user_filter = {**base_filter, "metadata.user_id": user_id}
			points = self._query(collection, user_filter, limit)
			if points:
				return points, "user_device"

		points = self._query(collection, base_filter, limit)
		return points, "device_fallback"

	@staticmethod
	def _query(
		collection, query_filter: dict[str, Any], limit: int
	) -> list[dict[str, Any]]:
		try:
			docs = list(
				collection.find(
					query_filter,
					{
						"_id": 0,
						"recorded_at": 1,
						"last_seen_at": 1,
						"metadata": 1,
						"sensors": 1,
						"network": 1,
					},
				)
				.sort("recorded_at", -1)
				.limit(limit)
			)
		except PyMongoError:
			return []
		return list(reversed(docs))

	@staticmethod
	def _series(points: list[dict[str, Any]], field: str) -> list[float]:
		values: list[float] = []
		for point in points:
			sensors = point.get("sensors")
			if not isinstance(sensors, dict):
				continue
			value = sensors.get(field)
			if isinstance(value, (int, float)):
				values.append(float(value))
		return values

	def _numeric_summary(
		self, points: list[dict[str, Any]], field: str
	) -> dict[str, Any]:
		values = self._series(points, field)
		if not values:
			return {"available": False}
		delta = values[-1] - values[0] if len(values) > 1 else 0.0
		return {
			"available": True,
			"current": round(values[-1], 3),
			"min": round(min(values), 3),
			"max": round(max(values), 3),
			"avg": round(mean(values), 3),
			"delta": round(delta, 3),
			"trend": self._trend(delta),
		}

	def _anomaly_events(self, points: list[dict[str, Any]]) -> dict[str, Any]:
		scores = self._series(points, "anomaly")
		if not scores:
			return {"available": False}
		event_count = sum(1 for score in scores if score > 0.5)
		critical_count = sum(1 for score in scores if score > 0.8)
		return {
			"available": True,
			"count": event_count,
			"critical_count": critical_count,
			"ratio": round(event_count / len(scores), 3),
			"latest_is_anomaly": scores[-1] > 0.5,
			"max_score": round(max(scores), 3),
		}

	def _stream_summary(self, points: list[dict[str, Any]]) -> dict[str, Any]:
		timestamps = [
			point.get("recorded_at")
			for point in points
			if isinstance(point.get("recorded_at"), datetime)
		]
		if len(timestamps) < 2:
			return {"available": False, "reason": "not_enough_points"}
		gaps = [
			max(0.0, (right - left).total_seconds())
			for left, right in zip(timestamps, timestamps[1:], strict=False)
		]
		return {
			"available": True,
			"avg_gap_seconds": round(mean(gaps), 2),
			"max_gap_seconds": round(max(gaps), 2),
		}

	@staticmethod
	def _trend(delta: float) -> str:
		if delta > 1.0:
			return "rising"
		if delta < -1.0:
			return "falling"
		return "stable"

	@staticmethod
	def _iso(value: Any) -> str | None:
		if isinstance(value, datetime):
			if value.tzinfo is None:
				value = value.replace(tzinfo=UTC)
			return value.isoformat()
		if isinstance(value, str):
			return value
		return None
