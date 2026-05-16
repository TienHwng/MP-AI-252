"""Stable user/device profile memory.

Phase 4 only reads this collection. Profile consolidation is intentionally
deferred so we do not spam durable preferences from every chat turn.
"""

from __future__ import annotations

from typing import Any

from pymongo.errors import PyMongoError

from memory.mongo_client import MongoMemoryClient


class ProfileStore:
	def __init__(self, mongo: MongoMemoryClient) -> None:
		self.mongo = mongo

	def get_profile(self, user_id: str) -> dict[str, Any]:
		collection = self.mongo.collection("user_profiles")
		if collection is None:
			return {}
		try:
			doc = collection.find_one({"user_id": user_id}, {"_id": 0})
		except PyMongoError:
			return {}
		return doc if isinstance(doc, dict) else {}
