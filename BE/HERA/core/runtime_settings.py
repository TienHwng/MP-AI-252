from __future__ import annotations

import os
import threading
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

YELLOW = "\033[93m"
RESET = "\033[0m"

DEFAULT_SETTINGS = {
	"provider": "openrouter",
	"models": {
		"ollama": {
			"orchestratorModel": "qwen2.5:1.5b",
			"deviceControlModel": "qwen2.5:7b",
			"sensorAnalysisModel": "qwen2.5:7b",
			"anomalyExpertModel": "qwen2.5:7b",
		},
		"openrouter": {
			"orchestratorModel": "qwen/qwen-2.5-7b-instruct",
			"deviceControlModel": "qwen/qwen-2.5-7b-instruct",
			"sensorAnalysisModel": "qwen/qwen-2.5-7b-instruct",
			"anomalyExpertModel": "qwen/qwen-2.5-7b-instruct",
		},
	},
}

MODEL_FIELDS = (
	"orchestratorModel",
	"deviceControlModel",
	"sensorAnalysisModel",
	"anomalyExpertModel",
)


def deep_merge(default: dict, override: dict) -> dict:
	result = dict(default)
	for key, value in override.items():
		if key in result and isinstance(result[key], dict) and isinstance(value, dict):
			result[key] = deep_merge(result[key], value)
		else:
			result[key] = value
	return result


def env_to_settings() -> dict:
	return {}


def prune_settings(settings: dict) -> dict:
	provider = settings.get("provider")
	result = {
		"provider": provider
		if provider in {"ollama", "openrouter"}
		else DEFAULT_SETTINGS["provider"],
		"models": {},
	}
	models = settings.get("models") if isinstance(settings.get("models"), dict) else {}
	for provider in ("ollama", "openrouter"):
		provider_models = (
			models.get(provider) if isinstance(models.get(provider), dict) else {}
		)
		result["models"][provider] = {
			field: value
			for field, value in provider_models.items()
			if field in MODEL_FIELDS
		}
	return result


class RuntimeSettingsStore:
	def __init__(self) -> None:
		root_env_path = Path(__file__).resolve().parents[2] / ".env"
		load_dotenv(dotenv_path=root_env_path)
		self.lock = threading.Lock()
		self.cache = deep_merge(DEFAULT_SETTINGS, env_to_settings())
		self.client: MongoClient | None = None
		self.collection = None
		try:
			mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
			mongo_db = os.getenv("MONGODB_DB", "HERA")
			self.client = MongoClient(mongo_uri)
			self.collection = self.client[mongo_db]["model_settings"]
			self.start_watch_thread()
		except Exception:
			self.client = None
			self.collection = None

	def load_from_db(self) -> dict | None:
		if self.collection is None:
			return None
		doc = self.collection.find_one({"_id": "hera_model_settings"})
		if not doc:
			return None
		return prune_settings(
			{
				"provider": doc.get("provider"),
				"models": doc.get("models", {}),
			}
		)

	def start_watch_thread(self) -> None:
		if self.collection is None:
			return

		def watch() -> None:
			try:
				with self.collection.watch(
					[{"$match": {"fullDocument._id": "hera_model_settings"}}],
					full_document="updateLookup",
				) as stream:
					for change in stream:
						full_document = change.get("fullDocument") or {}
						next_settings = {
							"provider": full_document.get("provider"),
							"models": full_document.get("models", {}),
						}
						next_settings = prune_settings(next_settings)
						with self.lock:
							prev_provider = self.cache.get("provider")
							self.cache = deep_merge(DEFAULT_SETTINGS, next_settings)
							current_provider = self.cache.get("provider")
						if current_provider != prev_provider:
							print(
								f"{YELLOW}[HERA][MODEL] Switched to provider: "
								f"{current_provider}{RESET}",
							)
			except PyMongoError:
				# Keep runtime resilient if change stream is unavailable.
				return

		thread = threading.Thread(target=watch, daemon=True)
		thread.start()

	def get(self) -> dict:
		with self.lock:
			latest = self.load_from_db()
			if latest:
				self.cache = deep_merge(DEFAULT_SETTINGS, latest)
			return deep_merge({}, self.cache)

	def get_provider(self) -> str:
		return self.get()["provider"]

	def get_model(self, provider: str, field: str) -> str:
		settings = self.get()
		return settings["models"].get(provider, {}).get(field, "")

	def get_active_model(self, field: str) -> str:
		settings = self.get()
		provider = settings["provider"]
		return settings["models"].get(provider, {}).get(field, "")

	def refresh_and_log(self) -> dict:
		"""
		Force refresh settings from DB and print a switch log immediately
		when provider changed.
		"""
		with self.lock:
			prev_provider = self.cache.get("provider")
			latest = self.load_from_db()
			if latest:
				self.cache = deep_merge(DEFAULT_SETTINGS, latest)
			current_provider = self.cache.get("provider")
			if current_provider != prev_provider:
				print(
					f"{YELLOW}[HERA][MODEL] Switched to provider: "
					f"{current_provider}{RESET}",
				)
			return deep_merge({}, self.cache)


runtime_settings = RuntimeSettingsStore()
