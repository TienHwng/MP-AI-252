"""Shared builders for the HERA web runtime."""

import logging

from agents.device_agent import DeviceControlAgent
from config import (
	DUCKDUCKGO_SEARCH_REGION,
	MODE,
	MONGODB_COLLECTION,
	MONGODB_DB,
	MONGODB_URI,
	MQTT_BROKER,
	MQTT_PORT,
	NEWS_CACHE_TTL_SECONDS,
	NEWS_DEFAULT_COUNTRY,
	NEWS_SEARCH_ENABLED,
	NEWSAPI_API_KEY,
	OPENWEATHERMAP_API_KEY,
	SPECIALIZED_SEARCH_ENABLED,
	WEATHER_CACHE_TTL_SECONDS,
	WEATHER_SEARCH_ENABLED,
	WEB_FETCH_TIMEOUT_SECONDS,
	WEB_SEARCH_DEFAULT_LOCATION,
	WEB_SEARCH_ENABLED,
	WEB_SEARCH_FETCH_TOP_RESULT,
	WEB_SEARCH_MAX_RESULTS,
	WEB_SEARCH_PROVIDER,
	WEB_SEARCH_TIMEOUT_SECONDS,
)
from core.llm_service import LLMService
from core.logger import log_hera, log_memory, log_mqtt
from core.mqtt_service import MQTTService
from core.runtime_settings import runtime_settings
from core.tool_registry import ToolRegistry
from domain.devices.device_executor import DeviceExecutor
from memory import MemoryService, MongoMemoryClient
from runtime import (
	CapabilityRegistry,
	PolicyEngine,
	ReadToolRunner,
	ToolRunner,
	VerificationService,
)
from services import AnomalyAnalyzerService, TelemetryReportService, WebResearchService
from telemetry import TelemetryStore
from web_search import (
	DuckDuckGoSearchService,
	NewsAPIService,
	OpenWeatherMapService,
	SearchIntentClassifier,
)

NOISY_LOGGERS = (
	"httpx",
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
	print("   HERA - Web IoT Assistant Runtime")
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
		persist_telemetry=True,
	)
	try:
		mqtt_svc.connect_client_only()
	except ConnectionRefusedError:
		log_mqtt("Cannot connect to MQTT broker")
		return None
	log_mqtt(f"Connected {MQTT_BROKER}:{MQTT_PORT}")
	return mqtt_svc


def build_runtime(mqtt_svc: MQTTService) -> tuple[ToolRegistry, ToolRunner]:
	capabilities = CapabilityRegistry()
	device_executor = DeviceExecutor(mqtt_svc)
	tool_runner = ToolRunner(
		capabilities,
		device_executor,
		policy_engine=PolicyEngine(),
		verification_service=VerificationService(),
	)
	tool_reg = ToolRegistry(
		mqtt_svc,
		capabilities=capabilities,
		device_executor=device_executor,
	)
	return tool_reg, tool_runner


def build_memory_service() -> MemoryService:
	mongo = MongoMemoryClient(MONGODB_URI, MONGODB_DB)
	if mongo.available:
		log_memory(f"MongoDB memory enabled: {MONGODB_DB}")
	else:
		log_memory("MongoDB unavailable; memory writes disabled")
	return MemoryService(mongo)


def build_web_search_service() -> DuckDuckGoSearchService:
	if WEB_SEARCH_PROVIDER != "duckduckgo":
		log_hera(
			f"Unsupported WEB_SEARCH_PROVIDER={WEB_SEARCH_PROVIDER}; using duckduckgo"
		)
	service = DuckDuckGoSearchService(
		enabled=WEB_SEARCH_ENABLED,
		default_max_results=WEB_SEARCH_MAX_RESULTS,
		search_timeout_seconds=WEB_SEARCH_TIMEOUT_SECONDS,
		fetch_timeout_seconds=WEB_FETCH_TIMEOUT_SECONDS,
		region=DUCKDUCKGO_SEARCH_REGION,
	)
	if service.available:
		log_hera("DuckDuckGo web search enabled")
	else:
		log_hera(f"DuckDuckGo web search unavailable: {service.unavailable_reason}")
	return service


def build_specialized_search_services() -> tuple[SearchIntentClassifier, dict]:
	classifier = SearchIntentClassifier(default_location=WEB_SEARCH_DEFAULT_LOCATION)
	if not SPECIALIZED_SEARCH_ENABLED:
		log_hera("Specialized web search disabled")
		return classifier, {}
	services = {
		"weather": OpenWeatherMapService(
			api_key=OPENWEATHERMAP_API_KEY,
			enabled=WEATHER_SEARCH_ENABLED,
			timeout_seconds=WEB_SEARCH_TIMEOUT_SECONDS,
			cache_ttl_seconds=WEATHER_CACHE_TTL_SECONDS,
			default_location=WEB_SEARCH_DEFAULT_LOCATION,
		),
		"news": NewsAPIService(
			api_key=NEWSAPI_API_KEY,
			enabled=NEWS_SEARCH_ENABLED,
			timeout_seconds=WEB_SEARCH_TIMEOUT_SECONDS,
			cache_ttl_seconds=NEWS_CACHE_TTL_SECONDS,
			default_country=NEWS_DEFAULT_COUNTRY,
		),
	}
	enabled = ", ".join(
		name
		for name, service in services.items()
		if getattr(service, "available", False)
	)
	log_hera(f"Specialized web search services ready: {enabled or 'fallback-only'}")
	return classifier, services


def build_agents(
	llm_svc: LLMService,
	mqtt_svc: MQTTService,
	tool_reg: ToolRegistry,
	tool_runner: ToolRunner,
	memory_service: MemoryService,
) -> dict:
	_ = tool_reg
	telemetry_store = TelemetryStore(
		memory_service.mongo,
		collection_name=MONGODB_COLLECTION,
	)
	read_tool_runner = ReadToolRunner(
		mqtt_svc,
		tool_runner.device_executor,
		telemetry_store,
	)
	web_search_service = build_web_search_service()
	intent_classifier, specialized_services = build_specialized_search_services()
	return {
		"device_control": DeviceControlAgent(llm_svc, tool_runner, telemetry_store),
		"telemetry_report": TelemetryReportService(mqtt_svc, read_tool_runner),
		"anomaly_analyzer": AnomalyAnalyzerService(
			mqtt_svc,
			telemetry_store,
			read_tool_runner,
		),
		"web_research": WebResearchService(
			web_search_service,
			max_results=WEB_SEARCH_MAX_RESULTS,
			fetch_top_result=WEB_SEARCH_FETCH_TOP_RESULT,
			intent_classifier=intent_classifier,
			specialized_services=specialized_services,
		),
	}


def print_runtime_summary(settings: dict, agents: dict) -> None:
	active_provider = settings["provider"]
	provider_models = settings["models"][active_provider]
	log_hera(f"Hardware mode: {MODE}")
	log_hera(f"Provider: {active_provider}")
	log_hera(f"Orchestrator model: {provider_models['orchestratorModel']}")
	log_hera(
		"Components: "
		f"device_control={provider_models['deviceControlModel']}, "
		"telemetry_report=deterministic, "
		"anomaly_analyzer=deterministic, "
		"web_research=duckduckgo"
	)
	log_hera(f"Runtime components: {', '.join(agents)}")
	log_hera("Web runtime components ready\n")


def main() -> None:
	configure_logging()
	print_banner()
	log_hera("Start the web API with: python backend/HERA/api_server.py")


if __name__ == "__main__":
	main()
