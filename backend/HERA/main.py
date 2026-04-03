"""
HERA - Multi-Agent IoT Telegram Bot
===================================
Entry point that wires together:
  core services -> agents -> orchestrator -> Telegram adapter

Run:
    cd backend/HERA
    python main.py
"""

import logging

import ollama
import openai

from config import (
    TELEGRAM_BOT_TOKEN,
    LLM_PROVIDER,
    OLLAMA_MODEL,
    OLLAMA_ROUTER_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    OPENROUTER_BASE_URL,
    MQTT_BROKER,
    MQTT_PORT,
    ORCHESTRATOR_MODEL_OLLAMA,
    ORCHESTRATOR_MODEL_OPENROUTER,
    DEVICE_AGENT_MODEL_OLLAMA,
    DEVICE_AGENT_MODEL_OPENROUTER,
    SENSOR_AGENT_MODEL_OLLAMA,
    SENSOR_AGENT_MODEL_OPENROUTER,
    ANOMALY_AGENT_MODEL_OLLAMA,
    ANOMALY_AGENT_MODEL_OPENROUTER,
    CHAT_AGENT_MODEL_OLLAMA,
    CHAT_AGENT_MODEL_OPENROUTER,
)
from core.llm_service import LLMService
from core.mqtt_service import MQTTService
from core.tool_registry import ToolRegistry

from agents.orchestrator import Orchestrator
from agents.device_agent import DeviceControlAgent
from agents.sensor_agent import SensorAnalysisAgent
from agents.anomaly_agent import AnomalyExpertAgent
from agents.chat_agent import ChatAgent

from adapters.telegram_adapter import TelegramAdapter

# ===================== LOGGING SETUP =====================
# Suppress verbose library logs
for lib in ["httpx", "telegram", "apscheduler", "paho.mqtt", "urllib3", "openai"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

# Configure main app logging (HERA, MQTT only)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",  # Simple: just show [HERA] ... [MQTT] ...
)


def _validate_ollama() -> bool:
    try:
        models = [m["name"] for m in ollama.list()["models"]]
        ok = True
        for needed in (OLLAMA_MODEL, OLLAMA_ROUTER_MODEL):
            if needed in models:
                print(f"  OK {needed}")
            else:
                print(f"  MISSING {needed}. Run: ollama pull {needed}")
                ok = False
        if not ok:
            print(f"  Available: {', '.join(models)}")
        return ok
    except Exception as exc:
        print(f"  Ollama unavailable: {exc}")
        return False


def _validate_openrouter() -> bool:
    if not OPENROUTER_API_KEY:
        print("  OPENROUTER_API_KEY not set in .env")
        return False
    try:
        print("  Verifying OpenRouter key ...")
        client = openai.OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )
        client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
        )
        print(f"  OpenRouter OK: {OPENROUTER_MODEL}")
        return True
    except Exception as exc:
        print(f"  OpenRouter error: {exc}")
        return False


# -- Provider selection -----------------------------------------
def select_llm_provider() -> str:
    print("\n" + "=" * 50)
    print("   HERA - Select LLM Provider")
    print("=" * 50)

    auto = LLM_PROVIDER if LLM_PROVIDER in {"ollama", "openrouter"} else None
    if auto:
        print(f"[HERA] Provider from .env: {auto}")
        if auto == "ollama" and _validate_ollama():
            return "ollama"
        if auto == "openrouter" and _validate_openrouter():
            return "openrouter"
        raise ValueError("Configured LLM_PROVIDER failed validation. Check .env")

    while True:
        print("\n1. Ollama (Local)")
        print("2. OpenRouter (Cloud)")
        choice = input("\nChoose (1/2): ").strip()

        if choice == "1":
            if _validate_ollama():
                return "ollama"
            continue

        if choice == "2":
            if _validate_openrouter():
                return "openrouter"
            continue

        print("  Enter 1 or 2.")


# -- Bootstrap --------------------------------------------------
def main() -> None:
    print("=" * 50)
    print("   HERA - Multi-Agent IoT Telegram Bot")
    print("=" * 50)

    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN not set in .env")
        return

    provider = select_llm_provider()

    mqtt_svc = MQTTService(broker_address=MQTT_BROKER, port=MQTT_PORT)
    try:
        mqtt_svc.connect()
        print(f"[MQTT] Connected {MQTT_BROKER}:{MQTT_PORT}")
    except ConnectionRefusedError:
        print("Cannot connect to MQTT broker")
        return

    llm_svc = LLMService(provider)
    tool_reg = ToolRegistry(mqtt_svc)

    agents = {
        "device_control": DeviceControlAgent(llm_svc, mqtt_svc, tool_reg),
        "sensor_analysis": SensorAnalysisAgent(llm_svc, mqtt_svc, tool_reg),
        "anomaly_expert": AnomalyExpertAgent(llm_svc, mqtt_svc),
        "chat": ChatAgent(llm_svc, mqtt_svc),
    }

    router_model = (
        ORCHESTRATOR_MODEL_OLLAMA
        if provider == "ollama"
        else ORCHESTRATOR_MODEL_OPENROUTER
    )
    orchestrator = Orchestrator(llm_svc, agents, router_model=router_model)

    telegram = TelegramAdapter(orchestrator, mqtt_svc, provider)

    if provider == "ollama":
        default_model = OLLAMA_MODEL
        agent_models = {
            "device_control": DEVICE_AGENT_MODEL_OLLAMA,
            "sensor_analysis": SENSOR_AGENT_MODEL_OLLAMA,
            "anomaly_expert": ANOMALY_AGENT_MODEL_OLLAMA,
            "chat": CHAT_AGENT_MODEL_OLLAMA,
        }
    else:
        default_model = OPENROUTER_MODEL
        agent_models = {
            "device_control": DEVICE_AGENT_MODEL_OPENROUTER,
            "sensor_analysis": SENSOR_AGENT_MODEL_OPENROUTER,
            "anomaly_expert": ANOMALY_AGENT_MODEL_OPENROUTER,
            "chat": CHAT_AGENT_MODEL_OPENROUTER,
        }

    print(f"[HERA] Provider: {provider} | Default model: {default_model}")
    print(f"[HERA] Router model: {router_model}")
    print(
        "[HERA] Agent models: "
        + ", ".join(f"{k}={v}" for k, v in agent_models.items())
    )
    print(f"[HERA] Agents: {', '.join(agents)}")
    print("[HERA] Bot running ... (Ctrl+C to stop)\n")

    telegram.run()


if __name__ == "__main__":
    main()
