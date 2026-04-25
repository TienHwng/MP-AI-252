"""Entry point for HERA Telegram bot runtime."""

import logging

from adapters.telegram_adapter import TelegramAdapter
from agents.anomaly_agent import AnomalyExpertAgent
from agents.device_agent import DeviceControlAgent
from agents.orchestrator import Orchestrator
from agents.sensor_agent import SensorAnalysisAgent
from agents.web_research_agent import WebResearchAgent
from config import (
	CALENDAR_CACHE_TTL_SECONDS,
	CALENDAR_SEARCH_ENABLED,
	DUCKDUCKGO_SEARCH_REGION,
	GOOGLE_CALENDAR_CREDENTIALS_PATH,
	GOOGLE_CALENDAR_ID,
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
	PLACES_CACHE_TTL_SECONDS,
	PLACES_SEARCH_ENABLED,
	PLACES_USER_AGENT,
	PRICE_CACHE_TTL_SECONDS,
	PRICE_DEFAULT_CURRENCY,
	PRICE_SEARCH_ENABLED,
	SPECIALIZED_SEARCH_ENABLED,
	TELEGRAM_BOT_TOKEN,
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
from runtime import CapabilityRegistry, PolicyEngine, ToolRunner, VerificationService
from telemetry import TelemetryStore
from web_search import (
	DuckDuckGoSearchService,
	GoogleCalendarService,
	NewsAPIService,
	NominatimPlacesService,
	OpenWeatherMapService,
	PriceSearchService,
	SearchIntentClassifier,
)

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
		"calendar": GoogleCalendarService(
			credentials_path=GOOGLE_CALENDAR_CREDENTIALS_PATH,
			enabled=CALENDAR_SEARCH_ENABLED,
			timeout_seconds=WEB_SEARCH_TIMEOUT_SECONDS,
			cache_ttl_seconds=CALENDAR_CACHE_TTL_SECONDS,
			calendar_id=GOOGLE_CALENDAR_ID,
		),
		"news": NewsAPIService(
			api_key=NEWSAPI_API_KEY,
			enabled=NEWS_SEARCH_ENABLED,
			timeout_seconds=WEB_SEARCH_TIMEOUT_SECONDS,
			cache_ttl_seconds=NEWS_CACHE_TTL_SECONDS,
			default_country=NEWS_DEFAULT_COUNTRY,
		),
		"price": PriceSearchService(
			enabled=PRICE_SEARCH_ENABLED,
			timeout_seconds=WEB_SEARCH_TIMEOUT_SECONDS,
			cache_ttl_seconds=PRICE_CACHE_TTL_SECONDS,
			default_currency=PRICE_DEFAULT_CURRENCY,
		),
		"places": NominatimPlacesService(
			enabled=PLACES_SEARCH_ENABLED,
			timeout_seconds=WEB_SEARCH_TIMEOUT_SECONDS,
			cache_ttl_seconds=PLACES_CACHE_TTL_SECONDS,
			default_location=WEB_SEARCH_DEFAULT_LOCATION,
			user_agent=PLACES_USER_AGENT,
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
	telemetry_store = TelemetryStore(
		memory_service.mongo,
		collection_name=MONGODB_COLLECTION,
	)
	web_search_service = build_web_search_service()
	intent_classifier, specialized_services = build_specialized_search_services()
	return {
		"device_control": DeviceControlAgent(llm_svc, tool_runner, telemetry_store),
		"sensor_analysis": SensorAnalysisAgent(llm_svc, mqtt_svc, tool_reg),
		"anomaly_expert": AnomalyExpertAgent(llm_svc, mqtt_svc, telemetry_store),
		"web_research": WebResearchAgent(
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
		"Agent models: "
		f"device_control={provider_models['deviceControlModel']}, "
		f"sensor_analysis={provider_models['sensorAnalysisModel']}, "
		f"anomaly_expert={provider_models['anomalyExpertModel']}, "
		"web_research=duckduckgo"
	)
	log_hera(f"Agents: {', '.join(agents)}")
	log_hera("Bot running ... (Ctrl+C to stop)\n")


def main() -> None:
	configure_logging()
	print_banner()

	if not TELEGRAM_BOT_TOKEN:
		log_hera("TELEGRAM_BOT_TOKEN not set in .env")
		return

	settings, provider = load_runtime_settings()
	mqtt_svc = connect_mqtt()
	if mqtt_svc is None:
		return

	llm_svc = LLMService(provider)
	tool_reg, tool_runner = build_runtime(mqtt_svc)
	memory_service = build_memory_service()
	agents = build_agents(llm_svc, mqtt_svc, tool_reg, tool_runner, memory_service)
	orchestrator = Orchestrator(
		llm_svc,
		agents,
		mqtt_svc,
		tool_runner=tool_runner,
		memory_service=memory_service,
		orchestrator_model=None,
	)
	print_runtime_summary(settings, agents)
	TelegramAdapter(orchestrator, mqtt_svc, provider).run()


if __name__ == "__main__":
	main()
