"""Action summary persistence for follow-up control and audit context."""

from __future__ import annotations

from typing import Any

from pymongo import DESCENDING
from pymongo.errors import PyMongoError
from schemas import ActionSummary

from memory.mongo_client import MongoMemoryClient


class ActionSummaryStore:
	def __init__(self, mongo: MongoMemoryClient) -> None:
		self.mongo = mongo

	def insert(self, summary: ActionSummary) -> bool:
		collection = self.mongo.collection("action_summaries")
		if collection is None:
			return False
		try:
			collection.insert_one(summary.model_dump(mode="python"))
		except PyMongoError:
			return False
		return True

	def recent_for_session(
		self,
		session_id: str,
		user_id: str,
		limit: int,
	) -> list[dict[str, Any]]:
		collection = self.mongo.collection("action_summaries")
		if collection is None:
			return []
		try:
			cursor = (
				collection.find(
					{"session_id": session_id, "user_id": user_id},
					{"_id": 0},
				)
				.sort("timestamp", DESCENDING)
				.limit(limit)
			)
			return list(cursor)
		except PyMongoError:
			return []
