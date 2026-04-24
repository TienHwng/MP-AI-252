"""Small MongoDB adapter used by HERA memory stores."""

from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError


class MongoMemoryClient:
	"""Owns the MongoDB connection for structured memory.

	The rest of the memory layer should degrade gracefully when this client is
	unavailable, so request handling is not coupled to Mongo uptime.
	"""

	def __init__(self, uri: str, db_name: str) -> None:
		self.uri = uri
		self.db_name = db_name
		self.client: MongoClient | None = None
		self.db: Database | None = None
		self.available = False
		try:
			self.client = MongoClient(uri, serverSelectionTimeoutMS=1000)
			self.client.admin.command("ping")
			self.db = self.client[db_name]
			self.available = True
		except PyMongoError:
			self.client = None
			self.db = None
			self.available = False

	def collection(self, name: str) -> Collection | None:
		if self.db is None:
			return None
		return self.db[name]

	def ensure_indexes(
		self, specs: dict[str, list[tuple[Any, dict[str, Any]]]]
	) -> None:
		if not self.available:
			return
		for collection_name, indexes in specs.items():
			collection = self.collection(collection_name)
			if collection is None:
				continue
			for keys, kwargs in indexes:
				try:
					collection.create_index(keys, **kwargs)
				except PyMongoError:
					continue
