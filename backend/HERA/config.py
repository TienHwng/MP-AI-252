"""
HERA Configuration
==================
Centralized settings for HERA.
All modules should import from here instead of reading .env directly.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load root .env file at startup
ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV_PATH)


# ===================== HELPER FUNCTIONS =====================


def env_int(name: str, default: int) -> int:
	"""Parse environment variable as integer."""
	try:
		return int(os.getenv(name))
	except (TypeError, ValueError):
		return default


def env_float(name: str, default: float) -> float:
	"""Parse environment variable as float."""
	try:
		return float(os.getenv(name))
	except (TypeError, ValueError):
		return default


def env_bool(name: str, default: bool) -> bool:
	raw = os.getenv(name)
	if raw is None:
		return default
	return raw.strip().lower() in {"1", "true", "yes", "on"}


# ===================== LLM PROVIDERS =====================

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
if not (os.getenv("OLLAMA_API_KEY") or "").strip() or OLLAMA_API_BASE.startswith(
	("http://localhost", "http://127.0.0.1")
):
	os.environ.pop("OLLAMA_API_KEY", None)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")


# ===================== WEB SEARCH =====================

WEB_SEARCH_PROVIDER = (
	(os.getenv("WEB_SEARCH_PROVIDER", "duckduckgo") or "duckduckgo").strip().lower()
)
WEB_SEARCH_ENABLED = env_bool("WEB_SEARCH_ENABLED", True)
WEB_SEARCH_MAX_RESULTS = env_int("WEB_SEARCH_MAX_RESULTS", 5)
WEB_SEARCH_TIMEOUT_SECONDS = env_float(
	"WEB_SEARCH_TIMEOUT_SECONDS",
	10.0,
)
WEB_FETCH_TIMEOUT_SECONDS = env_float(
	"WEB_FETCH_TIMEOUT_SECONDS",
	10.0,
)
WEB_SEARCH_FETCH_TOP_RESULT = env_bool("WEB_SEARCH_FETCH_TOP_RESULT", True)
WEB_SEARCH_DEFAULT_LOCATION = os.getenv(
	"WEB_SEARCH_DEFAULT_LOCATION",
	"Ho Chi Minh City, Vietnam",
)
DUCKDUCKGO_SEARCH_REGION = os.getenv("DUCKDUCKGO_SEARCH_REGION", "wt-wt")

SPECIALIZED_SEARCH_ENABLED = env_bool("SPECIALIZED_SEARCH_ENABLED", True)

WEATHER_SEARCH_ENABLED = env_bool("WEATHER_SEARCH_ENABLED", True)
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
WEATHER_CACHE_TTL_SECONDS = env_int("WEATHER_CACHE_TTL_SECONDS", 3600)

NEWS_SEARCH_ENABLED = env_bool("NEWS_SEARCH_ENABLED", True)
NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY")
NEWS_CACHE_TTL_SECONDS = env_int("NEWS_CACHE_TTL_SECONDS", 1800)
NEWS_DEFAULT_COUNTRY = os.getenv("NEWS_DEFAULT_COUNTRY", "vn")


# ===================== MQTT =====================


def env_mode() -> str:
	"""Runtime hardware mode: sim uses mqtt_simulator, real uses physical board."""
	raw = (os.getenv("MODE", "sim") or "sim").strip().lower()
	if raw in {"sim", "simulator", "simulation"}:
		return "sim"
	if raw in {"real", "hardware", "device"}:
		return "real"
	return "sim"


MODE = env_mode()

# Core MQTT connection
MQTT_BROKER = os.getenv("MQTT_BROKER", "10.0.2.131")
MQTT_BROKER_BIND_HOST = os.getenv("MQTT_BROKER_BIND_HOST", "10.0.2.131")
MQTT_PORT = env_int("MQTT_PORT", 1883)

# MQTT topics (migrated from old .env)
TOPIC_TELEMETRY = os.getenv("TOPIC_TELEMETRY", "v1/devices/me/telemetry")
TOPIC_RPC_REQUEST = os.getenv("TOPIC_RPC_REQUEST", "v1/devices/me/rpc/request/")
TOPIC_RPC_RESPONSE = os.getenv("TOPIC_RPC_RESPONSE", "v1/devices/me/rpc/response/")
TOPIC_ATTRIBUTES = os.getenv("TOPIC_ATTRIBUTES", "v1/devices/me/attributes")

# Backward-compatible MQTT topic names for existing modules
MQTT_SUBSCRIBE_TOPIC = os.getenv("MQTT_SUBSCRIBE_TOPIC", TOPIC_TELEMETRY)
MQTT_RPC_REQUEST_TOPIC_PREFIX = os.getenv(
	"MQTT_RPC_REQUEST_TOPIC_PREFIX",
	TOPIC_RPC_REQUEST.rstrip("/"),
).rstrip("/")


# ===================== MONGODB =====================

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "HERA")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "telemetry_points")
MEMORY_RECENT_ACTION_LIMIT = env_int("MEMORY_RECENT_ACTION_LIMIT", 8)
MEMORY_SESSION_TURN_LIMIT = env_int("MEMORY_SESSION_TURN_LIMIT", 40)


# ===================== AI THRESHOLDS =====================

# Temperature range (degrees Celsius)
NORMAL_TEMP_MIN = env_float("NORMAL_TEMP_MIN", 25.0)
NORMAL_TEMP_MAX = env_float("NORMAL_TEMP_MAX", 35.0)

# Humidity range (percentage)
NORMAL_HUMI_MIN = env_float("NORMAL_HUMI_MIN", 60.0)
NORMAL_HUMI_MAX = env_float("NORMAL_HUMI_MAX", 80.0)

# Anomaly scoring thresholds
ANOMALY_THRESHOLD = env_float("ANOMALY_THRESHOLD", 0.5)
ANOMALY_CRITICAL_THRESHOLD = env_float("ANOMALY_CRITICAL_THRESHOLD", 0.8)
TELEMETRY_STALE_SECONDS = env_int("TELEMETRY_STALE_SECONDS", 30)
ANOMALY_TELEMETRY_WINDOW_MINUTES = env_int("ANOMALY_TELEMETRY_WINDOW_MINUTES", 10)
ANOMALY_TELEMETRY_POINT_LIMIT = env_int("ANOMALY_TELEMETRY_POINT_LIMIT", 60)


# ===================== RUNTIME LIMITS =====================

MAX_TOOL_ITERATIONS = env_int("MAX_TOOL_ITERATIONS", 5)
MAX_HISTORY = env_int("MAX_HISTORY", 8)
DEVICE_VERIFICATION_TIMEOUT_SECONDS = env_float(
	"DEVICE_VERIFICATION_TIMEOUT_SECONDS", 0.8
)
DEVICE_VERIFICATION_POLL_SECONDS = env_float("DEVICE_VERIFICATION_POLL_SECONDS", 0.1)
GENERAL_RESPONSE_TIMEOUT_SECONDS = env_float("GENERAL_RESPONSE_TIMEOUT_SECONDS", 12.0)
FINAL_RESPONSE_TIMEOUT_SECONDS = env_float("FINAL_RESPONSE_TIMEOUT_SECONDS", 8.0)
