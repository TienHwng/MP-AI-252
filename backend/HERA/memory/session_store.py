"""Session thread persistence for short-term conversational memory."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo.errors import PyMongoError
from schemas import SessionTurn

from memory.mongo_client import MongoMemoryClient


class SessionStore:
	def __init__(self, mongo: MongoMemoryClient, *, turn_limit: int) -> None:
		self.mongo = mongo
		self.turn_limit = turn_limit

	def append_turn(self, turn: SessionTurn) -> bool:
		collection = self.mongo.collection("session_threads")
		if collection is None:
			return False
		payload = turn.model_dump(mode="python")
		try:
			collection.update_one(
				{"session_id": turn.session_id, "user_id": turn.user_id},
				{
					"$set": {
						"session_id": turn.session_id,
						"user_id": turn.user_id,
						"updated_at": datetime.now(),
					},
					"$push": {
						"turns": {
							"$each": [payload],
							"$slice": -self.turn_limit,
						}
					},
					"$setOnInsert": {"created_at": datetime.now()},
				},
				upsert=True,
			)
		except PyMongoError:
			return False
		return True

	def get_recent_turns(
		self, session_id: str, user_id: str, limit: int = 8
	) -> list[dict[str, Any]]:
		collection = self.mongo.collection("session_threads")
		if collection is None:
			return []
		try:
			doc = collection.find_one(
				{"session_id": session_id, "user_id": user_id},
				{"turns": {"$slice": -limit}},
			)
		except PyMongoError:
			return []
		turns = (doc or {}).get("turns", [])
		return turns if isinstance(turns, list) else []
