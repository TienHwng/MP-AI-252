"""Entry point for HERA Telegram bot runtime."""

import logging

from adapters.telegram_adapter import TelegramAdapter
from agents.anomaly_agent import AnomalyExpertAgent
from agents.device_agent import DeviceControlAgent
from agents.orchestrator import Orchestrator
from agents.sensor_agent import SensorAnalysisAgent
from config import MQTT_BROKER, MQTT_PORT, TELEGRAM_BOT_TOKEN
from core.llm_service import LLMService
from core.mqtt_service import MQTTService
from core.runtime_settings import runtime_settings
from core.tool_registry import ToolRegistry

NOISY_LOGGERS = (
    "httpx",
    "telegram",
    "apscheduler",
    "paho.mqtt",
    "urllib3",
    "openai",
    "amqtt",
    "transitions",
)


def configure_logging() -> None:
    for lib in NOISY_LOGGERS:
        logging.getLogger(lib).setLevel(logging.WARNING)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    litellm_logger = logging.getLogger("LiteLLM")
    litellm_logger.setLevel(logging.WARNING)
    litellm_logger.propagate = False


def print_banner() -> None:
    print("=" * 50)
    print("   HERA - Multi-Agent IoT Telegram Bot")
    print("=" * 50)


def load_runtime_settings() -> tuple[dict, str]:
    settings = runtime_settings.get()
    provider = settings["provider"]
    if provider not in {"ollama", "openrouter"}:
        raise ValueError(
            "Invalid runtime provider in model_settings. Use 'ollama' or 'openrouter'.",
        )
    return settings, provider


def connect_mqtt() -> MQTTService | None:
    mqtt_svc = MQTTService(
        broker_address=MQTT_BROKER,
        port=MQTT_PORT,
        persist_telemetry=False,
    )
    try:
        mqtt_svc.connect_client_only()
    except ConnectionRefusedError:
        print("Cannot connect to MQTT broker")
        return None
    print(f"[MQTT] Connected {MQTT_BROKER}:{MQTT_PORT}")
    return mqtt_svc


def build_agents(llm_svc: LLMService, mqtt_svc: MQTTService) -> dict:
    tool_reg = ToolRegistry(mqtt_svc)
    return {
        "device_control": DeviceControlAgent(llm_svc, mqtt_svc, tool_reg),
        "sensor_analysis": SensorAnalysisAgent(llm_svc, mqtt_svc, tool_reg),
        "anomaly_expert": AnomalyExpertAgent(llm_svc, mqtt_svc),
    }


def print_runtime_summary(settings: dict, agents: dict) -> None:
    active_provider = settings["provider"]
    provider_models = settings["models"][active_provider]
    print(f"[HERA] Provider: {active_provider}")
    print(f"[HERA] Orchestrator model: {provider_models['orchestratorModel']}")
    print(
        "[HERA] Agent models: "
        f"device_control={provider_models['deviceControlModel']}, "
        f"sensor_analysis={provider_models['sensorAnalysisModel']}, "
        f"anomaly_expert={provider_models['anomalyExpertModel']}"
    )
    print(f"[HERA] Agents: {', '.join(agents)}")
    print("[HERA] Bot running ... (Ctrl+C to stop)\n")


def main() -> None:
    configure_logging()
    print_banner()

    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN not set in .env")
        return

    settings, provider = load_runtime_settings()
    mqtt_svc = connect_mqtt()
    if mqtt_svc is None:
        return

    llm_svc = LLMService(provider)
    agents = build_agents(llm_svc, mqtt_svc)
    orchestrator = Orchestrator(llm_svc, agents, mqtt_svc, orchestrator_model=None)
    print_runtime_summary(settings, agents)
    TelegramAdapter(orchestrator, mqtt_svc, provider).run()


if __name__ == "__main__":
    main()
