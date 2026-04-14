"""
HERA Configuration
==================
Centralized settings loaded from environment variables (.env).
All modules import from here instead of reading .env directly.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load root .env file at startup
ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV_PATH)


# ===================== HELPER FUNCTIONS =====================

def _env_int(name: str, default: int) -> int:
    """Parse environment variable as integer."""
    try:
        return int(os.getenv(name))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    """Parse environment variable as float."""
    try:
        return float(os.getenv(name))
    except (TypeError, ValueError):
        return default


# ===================== TELEGRAM =====================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_READ_TIMEOUT = _env_int("TELEGRAM_READ_TIMEOUT", 30)
TELEGRAM_WRITE_TIMEOUT = _env_int("TELEGRAM_WRITE_TIMEOUT", 30)
TELEGRAM_CONNECT_TIMEOUT = _env_int("TELEGRAM_CONNECT_TIMEOUT", 30)


# ===================== LLM PROVIDERS =====================

# Provider lock: "ollama" or "openrouter" (None = interactive)
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "").strip().lower() or None

# Default models
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_ROUTER_MODEL = os.getenv("OLLAMA_ROUTER_MODEL")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")
OPENROUTER_ROUTER_MODEL = os.getenv("OPENROUTER_ROUTER_MODEL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")

# Orchestrator models (intent classifier)
ORCHESTRATOR_MODEL_OLLAMA = os.getenv("ORCHESTRATOR_MODEL_OLLAMA")
ORCHESTRATOR_MODEL_OPENROUTER = os.getenv("ORCHESTRATOR_MODEL_OPENROUTER")

# Device Agent models (LED/actuator control)
DEVICE_AGENT_MODEL_OLLAMA = os.getenv("DEVICE_AGENT_MODEL_OLLAMA")
DEVICE_AGENT_MODEL_OPENROUTER = os.getenv("DEVICE_AGENT_MODEL_OPENROUTER")

# Sensor Agent models (sensor interpretation)
SENSOR_AGENT_MODEL_OLLAMA = os.getenv("SENSOR_AGENT_MODEL_OLLAMA")
SENSOR_AGENT_MODEL_OPENROUTER = os.getenv("SENSOR_AGENT_MODEL_OPENROUTER")

# Anomaly Agent models (anomaly classification)
ANOMALY_AGENT_MODEL_OLLAMA = os.getenv("ANOMALY_AGENT_MODEL_OLLAMA")
ANOMALY_AGENT_MODEL_OPENROUTER = os.getenv("ANOMALY_AGENT_MODEL_OPENROUTER")

# Chat Agent models (general conversation fallback)
CHAT_AGENT_MODEL_OLLAMA = os.getenv("CHAT_AGENT_MODEL_OLLAMA")
CHAT_AGENT_MODEL_OPENROUTER = os.getenv("CHAT_AGENT_MODEL_OPENROUTER")


# ===================== MQTT =====================

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_BROKER_BIND_HOST = os.getenv("MQTT_BROKER_BIND_HOST")
MQTT_PORT = _env_int("MQTT_PORT", 1883)
MQTT_SUBSCRIBE_TOPIC = os.getenv("MQTT_SUBSCRIBE_TOPIC")
MQTT_RPC_REQUEST_TOPIC_PREFIX = os.getenv("MQTT_RPC_REQUEST_TOPIC_PREFIX")


# ===================== AI THRESHOLDS =====================

# Temperature range (degrees Celsius)
NORMAL_TEMP_MIN = _env_float("NORMAL_TEMP_MIN", 25.0)
NORMAL_TEMP_MAX = _env_float("NORMAL_TEMP_MAX", 35.0)

# Humidity range (percentage)
NORMAL_HUMI_MIN = _env_float("NORMAL_HUMI_MIN", 60.0)
NORMAL_HUMI_MAX = _env_float("NORMAL_HUMI_MAX", 80.0)

# Anomaly scoring thresholds
ANOMALY_THRESHOLD = _env_float("ANOMALY_THRESHOLD", 0.5)
ANOMALY_CRITICAL_THRESHOLD = _env_float("ANOMALY_CRITICAL_THRESHOLD", 0.8)


# ===================== RUNTIME LIMITS =====================

MAX_TOOL_ITERATIONS = _env_int("MAX_TOOL_ITERATIONS", 5)
MAX_HISTORY = _env_int("MAX_HISTORY", 8)

