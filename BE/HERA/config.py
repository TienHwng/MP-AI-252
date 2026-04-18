"""
HERA Configuration
==================
Centralized settings for HERA.
All modules should import from here instead of reading .env directly.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

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
	except TypeError, ValueError:
		return default


def env_float(name: str, default: float) -> float:
	"""Parse environment variable as float."""
	try:
		return float(os.getenv(name))
	except TypeError, ValueError:
		return default


# ===================== TELEGRAM =====================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_READ_TIMEOUT = env_int("TELEGRAM_READ_TIMEOUT", 30)
TELEGRAM_WRITE_TIMEOUT = env_int("TELEGRAM_WRITE_TIMEOUT", 30)
TELEGRAM_CONNECT_TIMEOUT = env_int("TELEGRAM_CONNECT_TIMEOUT", 30)


# ===================== LLM PROVIDERS =====================

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")


# ===================== MQTT =====================

# Core MQTT connection
MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.1.34")
MQTT_BROKER_BIND_HOST = os.getenv("MQTT_BROKER_BIND_HOST", "192.168.1.34")
MQTT_PORT = env_int("MQTT_PORT", 1883)

# MQTT topics (migrated from old .env)
TOPIC_TELEMETRY = os.getenv("TOPIC_TELEMETRY", "v1/devices/me/telemetry")
TOPIC_RPC_REQUEST = os.getenv("TOPIC_RPC_REQUEST", "v1/devices/me/rpc/request/")
TOPIC_RPC_RESPONSE = os.getenv("TOPIC_RPC_RESPONSE", "v1/devices/me/rpc/response/")
TOPIC_ATTRIBUTES = os.getenv("TOPIC_ATTRIBUTES", "v1/devices/me/attributes")

# Backward-compatible aliases for existing modules
MQTT_SUBSCRIBE_TOPIC = os.getenv("MQTT_SUBSCRIBE_TOPIC", TOPIC_TELEMETRY)
MQTT_RPC_REQUEST_TOPIC_PREFIX = os.getenv(
	"MQTT_RPC_REQUEST_TOPIC_PREFIX",
	TOPIC_RPC_REQUEST.rstrip("/"),
).rstrip("/")


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


# ===================== RUNTIME LIMITS =====================

MAX_TOOL_ITERATIONS = env_int("MAX_TOOL_ITERATIONS", 5)
MAX_HISTORY = env_int("MAX_HISTORY", 8)
