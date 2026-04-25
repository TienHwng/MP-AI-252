"""Behavior regression harness for HERA device-control semantics.

Run from BE/HERA:
    python tests_device_behavior.py
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import agents.device_agent as device_agent_module
import runtime.tool_runner as tool_runner_module
from agents.anomaly_agent import classify_anomaly
from agents.device_agent import DeviceControlAgent, build_tool_proposal
from agents.orchestrator import Orchestrator
from agents.web_research_agent import WebResearchAgent
from core.message import AgentResponse, MessageSource, UserMessage
from domain.devices.device_executor import DeviceExecutor
from prompts import (
	DEVICE_COMMAND_INTERPRETER_PROMPT,
	DEVICE_CONTROL_RESPONSE_SYSTEM,
	DEVICE_TARGET_CLARIFICATION_PROMPT,
	FINAL_RESPONSE_SYSTEM,
	GENERAL_SYSTEM,
	ROUTER_SYSTEM,
)
from runtime.capability_registry import CapabilityRegistry
from runtime.policy_engine import PolicyEngine
from runtime.tool_runner import ToolRunner
from schemas import MemoryContext
from web_search import DuckDuckGoSearchService, SearchIntentClassifier


class FakeLLM:
	"""Deterministic LLM double that exercises behavior guards."""

	def __init__(self) -> None:
		self.device_call_count = 0
		self.general_call_count = 0
		self.route_call_count = 0

	def completion(self, messages: list[dict], tools: Any, model: str) -> dict:
		system = messages[0]["content"]
		user = messages[-1]["content"]
		if system.startswith(ROUTER_SYSTEM):
			self.route_call_count += 1
			return {"content": json.dumps(self._route(user))}
		if system.startswith(DEVICE_COMMAND_INTERPRETER_PROMPT):
			self.device_call_count += 1
			return {"content": json.dumps(self._parse_command(user))}
		if system.startswith(DEVICE_TARGET_CLARIFICATION_PROMPT):
			self.device_call_count += 1
			return {"content": json.dumps(self._resolve_target(user))}
		if system.startswith(DEVICE_CONTROL_RESPONSE_SYSTEM):
			self.general_call_count += 1
			return {"content": self._compose_device_response(user)}
		if system.startswith(FINAL_RESPONSE_SYSTEM):
			self.general_call_count += 1
			return {"content": self._compose_final_response(user)}
		if system.startswith(GENERAL_SYSTEM.split("{time_context}", 1)[0]):
			self.general_call_count += 1
			return {"content": self._general_response(user)}
		self.general_call_count += 1
		raise AssertionError(f"Unexpected prompt in fake LLM: {system[:80]!r}")

	@staticmethod
	def _route(payload_text: str) -> dict:
		try:
			payload = json.loads(payload_text)
		except json.JSONDecodeError:
			payload = {"current_message": payload_text}
		text = str(payload.get("current_message") or payload_text).lower()
		default_location = str(
			payload.get("default_search_location") or "Ho Chi Minh City, Vietnam"
		)
		pending = payload.get("pending_device_clarification")
		pending_mode = "none"
		if isinstance(pending, dict):
			pending_mode = "new_request" if "nếu" in text else "clarification_answer"
		intent = "general"
		memory_scope = "none"
		direct_response = None
		web_query = None
		if "vừa rồi" in text and "thiết bị" in text:
			memory_scope = "actions"
		elif any(
			marker in text
			for marker in (
				"tìm web",
				"tìm kiếm",
				"search web",
				"tin mới",
				"mới nhất",
				"thời tiết",
			)
		):
			intent = "web_search"
			web_query = text
			if "thời tiết" in text and "mai" in text:
				web_query = (
					f"dự báo thời tiết {default_location} ngày 26/04/2026 có mưa không"
				)
		elif "bất thường" in text or "lưu ý" in text:
			intent = "anomaly_query"
		elif (
			"báo cáo tình hình" in text
			or "tình hình ngôi nhà" in text
			or (
				any(marker in text for marker in ("nhiệt độ", "độ ẩm", "ánh sáng"))
				and not any(marker in text for marker in ("bật", "tắt"))
			)
		):
			intent = "sensor_query"
		elif any(marker in text for marker in ("nếu", "bật", "tắt", "relay", "quạt")):
			intent = "device_control"
		if text.strip() in {"xin chào", "chào", "hello", "hi"}:
			direct_response = "Chào bạn, mình đây."
		if "bạn là ai" in text:
			direct_response = "Xin chào!"
		return {
			"intent": intent,
			"memory_scope": memory_scope,
			"direct_response": direct_response,
			"web_query": web_query,
			"pending_mode": pending_mode,
			"confidence": 0.9,
		}

	@staticmethod
	def _parse_command(text: str) -> dict:
		if "5 phút" in text and "20" in text and "quạt" in text:
			return {
				"action": "turn_on",
				"target": "mini_fan",
				"reference": "none",
				"confidence": 0.94,
				"condition": {
					"type": "sensor_window_threshold",
					"sensor": "temperature",
					"operator": ">",
					"threshold": 20,
					"window_seconds": 300,
				},
			}
		if "trên 40" in text and "quạt" in text:
			return {
				"action": "turn_on",
				"target": "all_lights",
				"reference": "recent_changed_devices",
				"confidence": 0.98,
				"condition": {
					"type": "sensor_threshold",
					"sensor": "temperature",
					"operator": ">",
					"threshold": 40,
				},
			}
		if "10 giây" in text and "35" in text and "quạt" in text:
			return {
				"action": "turn_on",
				"target": "mini_fan",
				"reference": "none",
				"confidence": 0.92,
				"condition": {
					"type": "sensor_window_threshold",
					"sensor": "temperature",
					"operator": ">=",
					"threshold": 35,
					"window_seconds": 10,
				},
			}
		if "trên 30" in text and "quạt" in text:
			return {
				"action": "turn_on",
				"target": "mini_fan",
				"reference": "none",
				"confidence": 0.92,
				"condition": {
					"type": "sensor_threshold",
					"sensor": "temperature",
					"operator": ">",
					"threshold": 30,
				},
			}
		if "các thiết bị khác" in text:
			return {
				"action": "turn_on",
				"target": "all_devices",
				"reference": "none",
				"confidence": 0.9,
			}
		if "tất cả thiết bị" in text:
			return {
				"action": "turn_on",
				"target": "all_devices",
				"reference": "none",
				"confidence": 0.9,
			}
		if "tất cả đèn" in text:
			return {
				"action": "turn_on",
				"target": "all_lights",
				"reference": "none",
				"confidence": 0.9,
			}
		if "vừa được bật" in text:
			return {
				"action": "turn_off",
				"target": None,
				"reference": "recent_changed_devices",
				"confidence": 0.9,
			}
		if "bật đèn" in text:
			# Simulate the bad model behavior we saw in Telegram logs.
			return {
				"action": "unknown",
				"target": "all_lights",
				"reference": "none",
				"confidence": 0.8,
			}
		return {
			"action": "unknown",
			"target": None,
			"reference": "none",
			"confidence": 0.0,
		}

	@staticmethod
	def _resolve_target(text: str) -> dict:
		if "neo" in text:
			return {"target": "neo_led", "confidence": 0.95}
		if "quạt" in text:
			return {"target": "mini_fan", "confidence": 0.95}
		if "tất cả đèn" in text:
			return {"target": "all_lights", "confidence": 0.95}
		return {"target": None, "confidence": 0.0}

	@staticmethod
	def _general_response(text: str) -> str:
		if "vừa rồi" in text:
			return "Mình chưa thấy bạn yêu cầu bật thiết bị nào ngay trước đó."
		if "hôm nay" in text:
			return "Hôm nay là Thứ Sáu, ngày 24/04/2026."
		if "trả lời câu trước" in text:
			return "Mình là HERA, trợ lý nhà thông minh của bạn."
		if "bạn là ai" in text:
			return "Mình là HERA, trợ lý nhà thông minh của bạn."
		return "Xin chào Tran, mình đây."

	@staticmethod
	def _compose_device_response(payload_text: str) -> str:
		payload = json.loads(payload_text)
		report = payload.get("specialist_report", {})
		analysis = report.get("analysis_payload", {})
		command = analysis.get("parsed_command", {})
		commands = analysis.get("parsed_commands", [])
		if isinstance(commands, list) and any(
			isinstance(item, dict)
			and item.get("action") in {"turn_on", "turn_off", "status"}
			and item.get("target") is None
			for item in commands
		):
			results = payload.get("execution_results", [])
			if results:
				return "Mình đã xử lý phần rõ ràng rồi. Còn phần đèn thì bạn muốn mình bật đèn nào?"
			return "Bạn muốn mình bật đèn nào?"
		condition = command.get("condition", {})
		if condition.get("status") == "not_met":
			if condition.get("type") == "sensor_window_threshold":
				return "Mình đã kiểm tra 10 giây gần đây: nhiệt độ chưa lên 35°C, nên mình chưa bật quạt."
			return "Mình đã kiểm tra nhiệt độ: hiện chưa trên 30°C, nên mình chưa bật quạt."
		results = payload.get("execution_results", [])
		if results and results[0].get("status") == "noop":
			return "Nhiệt độ đã vượt ngưỡng, nhưng quạt đang bật sẵn rồi."
		if results:
			return "Mình đã gửi lệnh điều khiển thiết bị."
		return "Mình cần làm rõ thêm trước khi điều khiển thiết bị."

	@staticmethod
	def _compose_final_response(payload_text: str) -> str:
		payload = json.loads(payload_text)
		route = payload.get("route_decision", {}).get("intent")
		if route == "anomaly_query":
			return "Mọi chỉ số hiện trong vùng an toàn, chưa có gì cần lưu ý đặc biệt."
		if route == "sensor_query":
			return "Hiện tại nhiệt độ 29.1°C, độ ẩm 37.6%, ánh sáng 420.0."
		if route == "web_search":
			return "Theo kết quả web, Ollama là nền tảng chạy mô hình AI. Nguồn: Ollama https://ollama.com/"
		return "Mình đã xem xong."


class FakeToolRunner:
	def get_device_status_report(self) -> dict:
		return {
			"main_led": False,
			"neo_led": False,
			"ws2812": False,
			"relay": False,
			"mini_fan": False,
		}


class FakeMemoryService:
	def __init__(self) -> None:
		self.mongo = type("FakeMongo", (), {"available": True})()
		self.retrieve_count = 0
		self.turn_write_count = 0
		self.tool_write_count = 0

	def retrieve(self, request):
		self.retrieve_count += 1
		raise AssertionError("simple device commands should not retrieve memory")

	def record_turn(self, request, response, *, intent: str) -> bool:
		self.turn_write_count += 1
		return True

	def record_tool_results(
		self, request, context, results, *, original_text: str
	) -> list:
		self.tool_write_count += 1
		return []


class FakeReadableMemoryService(FakeMemoryService):
	def __init__(self, recent_actions: list[dict] | None = None) -> None:
		super().__init__()
		self.recent_actions = recent_actions or []

	def retrieve(self, request):
		self.retrieve_count += 1
		return MemoryContext(
			available=True,
			recent_actions=self.recent_actions,
			recent_turns=[],
			user_profile={},
		)


class FakeTelemetryStore:
	def __init__(self, max_temperature: float, point_count: int = 4) -> None:
		self.max_temperature = max_temperature
		self.point_count = point_count
		self.calls: list[dict[str, Any]] = []

	def recent_summary_seconds(
		self,
		*,
		user_id: str | None,
		window_seconds: int,
		limit: int,
	) -> dict[str, Any]:
		self.calls.append(
			{
				"user_id": user_id,
				"window_seconds": window_seconds,
				"limit": limit,
			}
		)
		return {
			"available": True,
			"reason": "ok",
			"window_seconds": window_seconds,
			"point_limit": limit,
			"point_count": self.point_count,
			"first_recorded_at": "2026-04-24T15:20:00+00:00",
			"last_recorded_at": "2026-04-24T15:20:09+00:00",
			"temperature_c": {
				"available": True,
				"current": 27.3,
				"min": 27.1,
				"max": self.max_temperature,
				"avg": 28.0,
				"delta": 0.2,
				"trend": "stable",
			},
		}


class FakeWebSearchService:
	available = True
	unavailable_reason = None

	def __init__(self) -> None:
		self.search_calls: list[dict[str, Any]] = []
		self.fetch_calls: list[str] = []

	def search(self, query: str, max_results: int | None = None) -> dict[str, Any]:
		self.search_calls.append({"query": query, "max_results": max_results})
		return {
			"available": True,
			"status": "ok",
			"query": query,
			"max_results": max_results,
			"result_count": 1,
			"results": [
				{
					"title": "Ollama",
					"url": "https://ollama.com/",
					"content": "Ollama lets users run and build with AI models.",
				}
			],
		}

	def fetch(self, url: str) -> dict[str, Any]:
		self.fetch_calls.append(url)
		return {
			"available": True,
			"status": "ok",
			"url": url,
			"title": "Ollama",
			"content": "Ollama web page content.",
			"links": [],
		}


class FakeWeatherService:
	def __init__(self, status: str = "ok") -> None:
		self.status = status
		self.calls: list[dict[str, Any]] = []

	def forecast(
		self, location: str | None = None, days_ahead: int = 0
	) -> dict[str, Any]:
		self.calls.append({"location": location, "days_ahead": days_ahead})
		if self.status != "ok":
			return {
				"available": False,
				"status": "unavailable",
				"provider": "openweathermap",
				"reason": "missing_openweathermap_api_key",
				"results": [],
			}
		return {
			"available": True,
			"status": "ok",
			"provider": "openweathermap",
			"query": location,
			"data": {
				"location": location,
				"date": "2026-04-26",
				"temp_min": 25.0,
				"temp_max": 31.0,
				"condition": "mưa nhẹ",
				"rain_probability": 0.65,
				"humidity": 78,
				"wind_speed": 2.5,
			},
			"result_count": 1,
			"results": [
				{
					"title": "Weather forecast",
					"url": "https://openweathermap.org/",
					"content": "mưa nhẹ; 25.0-31.0°C; rain probability 65%",
				}
			],
		}


class FakeMQTT:
	def __init__(self) -> None:
		self.sensor_state = {
			"sensors": {
				"temperature": 29.1,
				"humidity": 37.55,
				"light": 420.0,
				"anomaly": 0.12,
			},
			"devices": {
				"led_status": False,
				"neo_led_status": False,
				"ws2812_status": False,
				"relay_status": False,
				"mini_fan_status": False,
			},
			"network": {"mqtt_connected": True},
			"last_seen_at": "2026-04-24T00:44:00+07:00",
		}
		self.published: list[tuple[str, Any]] = []

	def publish_rpc(self, method: str, params: Any) -> None:
		self.published.append((method, params))

	def get_device_snapshot(self) -> dict:
		return dict(self.sensor_state["devices"])

	def get_network_snapshot(self) -> dict:
		return dict(self.sensor_state["network"])

	def get_sensor_snapshot(self) -> dict:
		return dict(self.sensor_state)


def message(text: str) -> UserMessage:
	return UserMessage(
		text=text,
		chat_id="behavior-test",
		source=MessageSource.REST,
	)


async def parse(agent: DeviceControlAgent, text: str, recent_actions=None) -> dict:
	context = {
		"memory_context": {
			"recent_actions": recent_actions or [],
			"user_profile": {},
		}
	}
	return await agent.parse_command(message(text), context)


def assert_command(command: dict, *, action: str, target: str | None) -> None:
	assert command["action"] == action, command
	assert command["target"] == target, command


async def test_device_semantics() -> None:
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	agent = DeviceControlAgent(fake_llm, FakeToolRunner())

	generic_light = await parse(agent, "bật đèn lên giùm")
	assert_command(generic_light, action="turn_on", target=None)
	assert fake_llm.device_call_count == 0, fake_llm.device_call_count

	generic_led = await parse(agent, "bật đèn led giúp tôi")
	assert_command(generic_led, action="turn_on", target=None)
	assert fake_llm.device_call_count == 0, fake_llm.device_call_count

	all_lights = await parse(agent, "bật tất cả đèn")
	assert_command(all_lights, action="turn_on", target="all_lights")
	assert fake_llm.device_call_count == 0, fake_llm.device_call_count

	all_devices = await parse(agent, "bật tất cả thiết bị")
	assert_command(all_devices, action="turn_on", target="all_devices")
	assert fake_llm.device_call_count == 0, fake_llm.device_call_count

	parser_failed_group_command = await parse(
		agent,
		"tôi vừa đi làm về, mệt quá, hãy giúp tôi bật đèn và các thiết bị khác lên nhé",
	)
	assert_command(parser_failed_group_command, action="turn_on", target="all_devices")

	recent_light_group = [
		{"changed_entities": ["Main LED", "NeoPixel LED", "WS2812 LED"]}
	]
	follow_up = await parse(
		agent,
		"tắt những thiết bị vừa được bật",
		recent_light_group,
	)
	assert_command(follow_up, action="turn_off", target="all_lights")

	typo_follow_up = await parse(
		agent,
		"ắt những thiết bị vừa được bật",
		recent_light_group,
	)
	assert_command(typo_follow_up, action="turn_off", target="all_lights")

	explicit_main_led = await parse(agent, "bật main led giúp tôi")
	assert_command(explicit_main_led, action="turn_on", target="main_led")

	explicit_device = await parse(agent, "bật đèn neo giúp tôi")
	assert_command(explicit_device, action="turn_on", target="neo_led")
	assert fake_llm.device_call_count <= 3, fake_llm.device_call_count


async def test_target_resolution_from_clarification() -> None:
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	agent = DeviceControlAgent(fake_llm, FakeToolRunner())
	result = await agent.resolve_target_from_clarification(
		message("đèn neo"),
		requested_action="turn_on",
	)
	assert result["target"] == "neo_led", result
	assert fake_llm.device_call_count == 0, fake_llm.device_call_count


async def test_fast_confirmation_and_direct_device_rendering() -> None:
	orchestrator = Orchestrator(
		FakeLLM(),
		{},
		FakeMQTT(),
	)
	assert await orchestrator.classify_pending_confirmation("ừ, xác nhận") == "confirm"
	text = orchestrator.render_device_control_text(
		"bật đèn giùm tôi đi",
		{
			"status": "ask",
			"policy_reason": "broad_all_devices_scope_requires_confirmation",
			"user_visible_message": None,
		},
	)
	assert "xác nhận" in text.lower(), text


async def test_device_clarification_payload_is_serializable() -> None:
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	agent = DeviceControlAgent(FakeLLM(), FakeToolRunner())
	response = await agent.process(
		message("bật đèn giúp tôi"),
		{
			"memory_context": {
				"recent_actions": [],
				"user_profile": {},
			}
		},
	)
	json.dumps(response.metadata, ensure_ascii=False)


async def test_fast_device_intent_routing() -> None:
	orchestrator = Orchestrator(
		FakeLLM(),
		{},
		FakeMQTT(),
	)
	assert await orchestrator.classify_intent("bật đèn lên giùm") == "device_control"
	assert (
		await orchestrator.classify_intent("relay đang bật hay tắt") == "device_control"
	)
	assert (
		await orchestrator.classify_intent("báo cáo tình hình ngôi nhà")
		== "sensor_query"
	)
	assert (
		await orchestrator.classify_intent("vậy có gì cần lưu ý không")
		== "anomaly_query"
	)
	assert (
		await orchestrator.classify_intent(
			"ừa, kiểm tra xem 5 phút vừa rồi có lúc nào nhiệt độ trên 20 độ không, nếu có thì bật quạt giúp tôi nhé"
		)
		== "device_control"
	)


async def test_fast_read_only_routing_and_rendering() -> None:
	fake_llm = FakeLLM()
	fake_mqtt = FakeMQTT()
	orchestrator = Orchestrator(
		fake_llm,
		{},
		fake_mqtt,
	)
	assert (
		await orchestrator.classify_intent("nhiệt độ hiện tại bao nhiêu")
		== "sensor_query"
	)
	assert await orchestrator.classify_intent("có bất thường không") == "anomaly_query"
	assert (
		await orchestrator.classify_intent("hôm nay là thứ mấy, ngày mấy") == "general"
	)
	assert (
		await orchestrator.classify_intent("tìm kiếm tin mới nhất về Ollama")
		== "web_search"
	)

	general = await orchestrator.handle_general(message("xin chào"))
	assert "mình đây" in general.text.lower(), general.text
	assert fake_llm.general_call_count == 1, fake_llm.general_call_count

	date_response = await orchestrator.handle_general(
		message("hôm nay là thứ mấy, ngày mấy")
	)
	assert "24/04/2026" in date_response.text, date_response.text
	assert fake_llm.general_call_count == 2, fake_llm.general_call_count

	sensor_response = orchestrator.render_sensor_text(
		"nhiệt độ hiện tại bao nhiêu",
		AgentResponse(
			text="",
			agent_name="sensor_analysis",
			metadata={
				"specialist_report": {
					"analysis_payload": {
						"snapshot": fake_mqtt.get_sensor_snapshot(),
					}
				}
			},
		),
	)
	assert "29.1" in sensor_response, sensor_response


async def test_identity_questions_do_not_use_router_direct_response() -> None:
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	orchestrator = Orchestrator(
		fake_llm,
		{},
		FakeMQTT(),
		memory_service=FakeMemoryService(),
	)

	response = await orchestrator.handle(message("xin chào, bạn là ai"))

	assert "hera" in response.text.lower(), response.text
	assert "google" not in response.text.lower(), response.text
	assert "mô hình ngôn ngữ" not in response.text.lower(), response.text
	assert not response.metadata.get("route_direct_response"), response.metadata


async def test_answer_previous_followup_uses_conversation_context() -> None:
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	orchestrator = Orchestrator(
		fake_llm,
		{},
		FakeMQTT(),
		memory_service=FakeMemoryService(),
	)

	await orchestrator.handle(message("xin chào, bạn là ai"))
	response = await orchestrator.handle(message("trả lời câu trước đi"))

	assert "hera" in response.text.lower(), response.text
	assert "google" not in response.text.lower(), response.text
	assert "mô hình ngôn ngữ" not in response.text.lower(), response.text

	anomaly_response = orchestrator.render_anomaly_text(
		"có bất thường không",
		AgentResponse(
			text="",
			agent_name="anomaly_expert",
			metadata={
				"specialist_report": {
					"analysis_payload": {
						"classification": {
							"type": "normal",
							"severity": "none",
							"score": 0.12,
							"detail": "All readings within normal range.",
						},
						"freshness": {
							"is_stale": False,
						},
						"telemetry_window": {
							"anomaly_events": {"available": True, "count": 0},
						},
					}
				}
			},
		),
	)
	assert "bất thường" in anomaly_response.lower(), anomaly_response


async def test_fast_device_pipeline_skips_memory_and_parser_llm() -> None:
	tool_runner_module.DEVICE_VERIFICATION_TIMEOUT_SECONDS = 0
	tool_runner_module.DEVICE_VERIFICATION_POLL_SECONDS = 0
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	fake_mqtt = FakeMQTT()
	runner = ToolRunner(
		CapabilityRegistry(),
		DeviceExecutor(fake_mqtt),
		policy_engine=PolicyEngine(),
	)
	memory = FakeMemoryService()
	orchestrator = Orchestrator(
		fake_llm,
		{"device_control": DeviceControlAgent(fake_llm, runner)},
		fake_mqtt,
		tool_runner=runner,
		memory_service=memory,
	)

	response = await orchestrator.handle(message("bật đèn phòng khách giúp tôi"))

	assert fake_llm.device_call_count == 0, fake_llm.device_call_count
	assert memory.retrieve_count == 0, memory.retrieve_count
	assert memory.turn_write_count == 1, memory.turn_write_count
	assert memory.tool_write_count == 0, memory.tool_write_count
	assert fake_mqtt.published == []
	assert "đèn nào" in response.text.lower(), response.text
	assert fake_llm.device_call_count == 0, fake_llm.device_call_count
	assert fake_llm.general_call_count == 1, fake_llm.general_call_count


async def test_simple_general_pipeline_skips_memory_retrieval() -> None:
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	memory = FakeMemoryService()
	orchestrator = Orchestrator(
		fake_llm,
		{},
		FakeMQTT(),
		memory_service=memory,
	)

	response = await orchestrator.handle(message("xin chào"))

	assert memory.retrieve_count == 0, memory.retrieve_count
	assert memory.turn_write_count == 1, memory.turn_write_count
	assert "mình" in response.text.lower(), response.text
	assert fake_llm.route_call_count == 1, fake_llm.route_call_count
	assert fake_llm.general_call_count == 0, fake_llm.general_call_count


async def test_action_memory_question_is_not_device_control() -> None:
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	memory = FakeReadableMemoryService()
	runner = ToolRunner(
		CapabilityRegistry(),
		DeviceExecutor(FakeMQTT()),
		policy_engine=PolicyEngine(),
	)
	orchestrator = Orchestrator(
		fake_llm,
		{"device_control": DeviceControlAgent(fake_llm, runner)},
		FakeMQTT(),
		tool_runner=runner,
		memory_service=memory,
	)

	response = await orchestrator.handle(
		message("vừa rồi tôi đã kêu bạn bật thiết bị nào chưa")
	)

	assert response.metadata["intent"] == "general", response.metadata
	assert memory.retrieve_count == 1, memory.retrieve_count
	assert fake_llm.device_call_count == 0, fake_llm.device_call_count
	assert fake_llm.route_call_count == 1, fake_llm.route_call_count
	assert "which device" not in response.text.lower(), response.text


async def test_conditional_device_request_checks_sensor_before_acting() -> None:
	tool_runner_module.DEVICE_VERIFICATION_TIMEOUT_SECONDS = 0
	tool_runner_module.DEVICE_VERIFICATION_POLL_SECONDS = 0
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	fake_mqtt = FakeMQTT()
	runner = ToolRunner(
		CapabilityRegistry(),
		DeviceExecutor(fake_mqtt),
		policy_engine=PolicyEngine(),
	)
	orchestrator = Orchestrator(
		fake_llm,
		{"device_control": DeviceControlAgent(fake_llm, runner)},
		fake_mqtt,
		tool_runner=runner,
		memory_service=FakeMemoryService(),
	)

	response = await orchestrator.handle(
		message(
			"kiểm tra xem nhiệt độ có cao không, nếu trên 30 độ thì bật quạt giúp tôi"
		)
	)

	assert fake_mqtt.published == [], fake_mqtt.published
	assert "chưa bật quạt" in response.text.lower(), response.text
	assert (
		response.metadata["specialist_report"]["analysis_payload"]["parsed_command"][
			"action"
		]
		== "turn_on"
	)
	assert fake_llm.device_call_count == 1, fake_llm.device_call_count


async def test_temporal_condition_checks_telemetry_window_before_acting() -> None:
	tool_runner_module.DEVICE_VERIFICATION_TIMEOUT_SECONDS = 0
	tool_runner_module.DEVICE_VERIFICATION_POLL_SECONDS = 0
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	fake_mqtt = FakeMQTT()
	telemetry = FakeTelemetryStore(max_temperature=34.8)
	runner = ToolRunner(
		CapabilityRegistry(),
		DeviceExecutor(fake_mqtt),
		policy_engine=PolicyEngine(),
	)
	orchestrator = Orchestrator(
		fake_llm,
		{"device_control": DeviceControlAgent(fake_llm, runner, telemetry)},
		fake_mqtt,
		tool_runner=runner,
		memory_service=FakeMemoryService(),
	)
	orchestrator.graph.update_thread_state(
		"behavior-test",
		{
			"pending_device_clarification": {
				"request_id": "previous",
				"requested_action": "turn_on",
				"clarification_question": "Bạn muốn mình điều khiển thiết bị nào?",
			}
		},
	)

	response = await orchestrator.handle(
		message(
			"kiếm tra giúp tôi xem nếu tong 10 giây vừa rồi có lúc nào nhiệt độ lên 35 độ thì bật quạt giúp tôi nhé"
		)
	)

	assert telemetry.calls and telemetry.calls[0]["window_seconds"] == 10
	assert fake_mqtt.published == [], fake_mqtt.published
	assert "chưa" in response.text.lower(), response.text
	parsed = response.metadata["specialist_report"]["analysis_payload"][
		"parsed_command"
	]
	assert parsed["condition"]["type"] == "sensor_window_threshold", parsed
	assert parsed["condition"]["status"] == "not_met", parsed
	assert (
		orchestrator.graph.get_thread_state("behavior-test").get(
			"pending_device_clarification"
		)
		is None
	)
	assert fake_llm.device_call_count == 1, fake_llm.device_call_count


async def test_temporal_conditional_device_request_bypasses_bad_router() -> None:
	tool_runner_module.DEVICE_VERIFICATION_TIMEOUT_SECONDS = 0
	tool_runner_module.DEVICE_VERIFICATION_POLL_SECONDS = 0
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	fake_mqtt = FakeMQTT()
	telemetry = FakeTelemetryStore(max_temperature=23.4)
	runner = ToolRunner(
		CapabilityRegistry(),
		DeviceExecutor(fake_mqtt),
		policy_engine=PolicyEngine(),
	)
	orchestrator = Orchestrator(
		fake_llm,
		{"device_control": DeviceControlAgent(fake_llm, runner, telemetry)},
		fake_mqtt,
		tool_runner=runner,
		memory_service=FakeMemoryService(),
	)

	response = await orchestrator.handle(
		message(
			"ừa, kiểm tra xem 5 phút vừa rồi có lúc nào nhiệt độ trên 20 độ không, nếu có thì bật quạt giúp tôi nhé"
		)
	)

	assert fake_llm.route_call_count == 0, fake_llm.route_call_count
	assert telemetry.calls and telemetry.calls[0]["window_seconds"] == 300
	assert fake_mqtt.published == [("setValueMiniFan", True)], fake_mqtt.published
	assert response.metadata["intent"] == "device_control", response.metadata
	parsed = response.metadata["specialist_report"]["analysis_payload"][
		"parsed_command"
	]
	assert parsed["condition"]["type"] == "sensor_window_threshold", parsed
	assert parsed["condition"]["status"] == "met", parsed
	assert parsed["target"] == "mini_fan", parsed


async def test_conditional_noop_response_stays_vietnamese() -> None:
	tool_runner_module.DEVICE_VERIFICATION_TIMEOUT_SECONDS = 0
	tool_runner_module.DEVICE_VERIFICATION_POLL_SECONDS = 0
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	fake_mqtt = FakeMQTT()
	fake_mqtt.sensor_state["sensors"]["temperature"] = 31.2
	fake_mqtt.sensor_state["devices"]["mini_fan_status"] = True
	runner = ToolRunner(
		CapabilityRegistry(),
		DeviceExecutor(fake_mqtt),
		policy_engine=PolicyEngine(),
	)
	orchestrator = Orchestrator(
		fake_llm,
		{"device_control": DeviceControlAgent(fake_llm, runner)},
		fake_mqtt,
		tool_runner=runner,
		memory_service=FakeMemoryService(),
	)

	response = await orchestrator.handle(
		message("nếu nhiệt độ trên 30 độ thì bật quạt giúp tôi")
	)

	assert fake_mqtt.published == [], fake_mqtt.published
	assert "quạt đang bật sẵn" in response.text.lower(), response.text
	assert "requested device state" not in response.text.lower(), response.text
	assert fake_llm.device_call_count == 1, fake_llm.device_call_count


async def test_conditional_command_prefers_explicit_target_over_recent_actions() -> (
	None
):
	tool_runner_module.DEVICE_VERIFICATION_TIMEOUT_SECONDS = 0
	tool_runner_module.DEVICE_VERIFICATION_POLL_SECONDS = 0
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	fake_mqtt = FakeMQTT()
	fake_mqtt.sensor_state["sensors"]["temperature"] = 41.5
	runner = ToolRunner(
		CapabilityRegistry(),
		DeviceExecutor(fake_mqtt),
		policy_engine=PolicyEngine(),
	)
	memory = FakeReadableMemoryService(
		recent_actions=[
			{"changed_entities": ["Main LED", "NeoPixel LED", "WS2812 LED"]}
		]
	)
	orchestrator = Orchestrator(
		fake_llm,
		{"device_control": DeviceControlAgent(fake_llm, runner)},
		fake_mqtt,
		tool_runner=runner,
		memory_service=memory,
	)

	response = await orchestrator.handle(
		message(
			"kiểm tra xem nhiệt độ có đang trên 40 dô không, nếu có thì bật quạt giúp tôi đi"
		)
	)

	assert fake_mqtt.published == [("setValueMiniFan", True)], fake_mqtt.published
	parsed = response.metadata["specialist_report"]["analysis_payload"][
		"parsed_command"
	]
	assert parsed["target"] == "mini_fan", parsed
	assert parsed["reference"] == "none", parsed


async def test_multi_action_keeps_condition_scoped_per_action() -> None:
	tool_runner_module.DEVICE_VERIFICATION_TIMEOUT_SECONDS = 0
	tool_runner_module.DEVICE_VERIFICATION_POLL_SECONDS = 0
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	fake_mqtt = FakeMQTT()
	fake_mqtt.sensor_state["sensors"]["temperature"] = 28.82
	runner = ToolRunner(
		CapabilityRegistry(),
		DeviceExecutor(fake_mqtt),
		policy_engine=PolicyEngine(),
	)
	orchestrator = Orchestrator(
		fake_llm,
		{"device_control": DeviceControlAgent(fake_llm, runner)},
		fake_mqtt,
		tool_runner=runner,
		memory_service=FakeMemoryService(),
	)

	response = await orchestrator.handle(
		message(
			"ừ, xem xem nhiệt độ có trên 40 độ không, nếu có bật giúp tôi cái quạt, với tiện thể bật giùm cái đèn luôn nha"
		)
	)

	assert fake_mqtt.published == [], fake_mqtt.published
	analysis = response.metadata["specialist_report"]["analysis_payload"]
	commands = analysis["parsed_commands"]
	assert len(commands) == 2, commands
	assert commands[0]["target"] == "mini_fan", commands
	assert commands[0]["condition"]["status"] == "not_met", commands
	assert commands[1]["target"] is None, commands
	assert "đèn nào" in response.text.lower(), response.text
	assert (
		orchestrator.graph.get_thread_state("behavior-test")
		.get("pending_device_clarification", {})
		.get("requested_action")
		== "turn_on"
	)


async def test_short_device_followups_use_conversation_focus() -> None:
	tool_runner_module.DEVICE_VERIFICATION_TIMEOUT_SECONDS = 0
	tool_runner_module.DEVICE_VERIFICATION_POLL_SECONDS = 0
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	fake_mqtt = FakeMQTT()
	runner = ToolRunner(
		CapabilityRegistry(),
		DeviceExecutor(fake_mqtt),
		policy_engine=PolicyEngine(),
	)
	orchestrator = Orchestrator(
		fake_llm,
		{"device_control": DeviceControlAgent(fake_llm, runner)},
		fake_mqtt,
		tool_runner=runner,
		memory_service=FakeMemoryService(),
	)

	status = await orchestrator.handle(message("relay có đang bật không nhỉ"))
	assert status.metadata["intent"] == "device_control", status.metadata
	assert (
		orchestrator.graph.get_thread_state("behavior-test")
		.get("active_focus", {})
		.get("target")
		== "relay"
	)

	await orchestrator.handle(message("bật đi"))
	assert fake_mqtt.published == [("setValueRelay", True)], fake_mqtt.published

	check = await orchestrator.handle(message("chắc chưa"))
	parsed = check.metadata["specialist_report"]["analysis_payload"]["parsed_command"]
	assert parsed["action"] == "status", parsed
	assert parsed["target"] == "relay", parsed


async def test_web_search_pipeline_uses_search_service() -> None:
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	web_service = FakeWebSearchService()
	orchestrator = Orchestrator(
		fake_llm,
		{"web_research": WebResearchAgent(web_service)},
		FakeMQTT(),
		memory_service=FakeMemoryService(),
	)

	response = await orchestrator.handle(message("tìm kiếm tin mới nhất về Ollama"))

	assert response.metadata["intent"] == "web_search", response.metadata
	assert web_service.search_calls, web_service.search_calls
	assert web_service.search_calls[0]["max_results"] == 5
	assert "ollama" in web_service.search_calls[0]["query"].lower()
	assert "nguồn" in response.text.lower(), response.text
	assert fake_llm.route_call_count == 1, fake_llm.route_call_count
	assert fake_llm.general_call_count == 1, fake_llm.general_call_count


async def test_weather_web_query_is_grounded_with_date_and_location() -> None:
	device_agent_module.runtime_settings.get_active_model = lambda _field: "fake-model"
	fake_llm = FakeLLM()
	web_service = FakeWebSearchService()
	orchestrator = Orchestrator(
		fake_llm,
		{"web_research": WebResearchAgent(web_service)},
		FakeMQTT(),
		memory_service=FakeMemoryService(),
	)

	response = await orchestrator.handle(
		message("xin chào, xem giùm thời tiết xem mai có thể có mưa không nhỉ")
	)

	query = web_service.search_calls[0]["query"].lower()
	assert response.metadata["intent"] == "web_search", response.metadata
	assert "ho chi minh city" in query, query
	assert "26/04/2026" in query, query
	assert web_service.fetch_calls == ["https://ollama.com/"], web_service.fetch_calls


def test_specialized_intent_classifier_supports_vietnamese_and_english() -> None:
	classifier = SearchIntentClassifier(default_location="Ho Chi Minh City, Vietnam")
	assert classifier.classify("mai thời tiết có mưa không").intent == "weather"
	assert classifier.classify("latest AI news").intent == "news"
	assert classifier.classify("bitcoin price in usd").intent == "price"
	assert classifier.classify("quán cafe gần đây").intent == "places"
	assert classifier.classify("lịch họp ngày mai").intent == "calendar"
	assert classifier.classify("what is ollama").intent == "generic"


async def test_web_research_uses_specialized_weather_service() -> None:
	web_service = FakeWebSearchService()
	weather = FakeWeatherService()
	agent = WebResearchAgent(
		web_service,
		intent_classifier=SearchIntentClassifier(
			default_location="Ho Chi Minh City, Vietnam"
		),
		specialized_services={"weather": weather},
	)

	response = await agent.process(
		message("xem thời tiết ngày mai ở Ho Chi Minh City"),
		{"route_plan": {"web_query": "thời tiết Ho Chi Minh City ngày mai"}},
	)

	payload = response.metadata["web_research"]
	assert payload["search_intent"]["intent"] == "weather", payload
	assert payload["search"]["provider"] == "openweathermap", payload
	assert weather.calls and weather.calls[0]["days_ahead"] == 1
	assert web_service.search_calls == [], web_service.search_calls


async def test_web_research_falls_back_when_specialized_unavailable() -> None:
	web_service = FakeWebSearchService()
	weather = FakeWeatherService(status="unavailable")
	agent = WebResearchAgent(
		web_service,
		intent_classifier=SearchIntentClassifier(
			default_location="Ho Chi Minh City, Vietnam"
		),
		specialized_services={"weather": weather},
	)

	response = await agent.process(
		message("xem thời tiết ngày mai"),
		{"route_plan": {"web_query": "thời tiết Ho Chi Minh City ngày mai"}},
	)

	payload = response.metadata["web_research"]
	assert payload["search_intent"]["intent"] == "weather", payload
	assert payload["specialized_error"]["reason"] == "missing_openweathermap_api_key"
	assert payload["tool_results"][1]["name"] == "search_web", payload
	assert web_service.search_calls, web_service.search_calls


def test_duckduckgo_web_search_service_disabled_without_network() -> None:
	service = DuckDuckGoSearchService(enabled=False)
	result = service.search("what is ollama?")
	assert result["status"] == "unavailable", result
	assert result["reason"] == "web_search_disabled", result


def test_all_devices_confirmation_policy() -> None:
	policy = PolicyEngine()
	capability = CapabilityRegistry().require("turn_on_device")
	proposal = build_tool_proposal(
		{"action": "turn_on", "target": "all_devices", "confidence": 1.0}
	)
	assert proposal is not None
	state = {
		"network": {"mqtt_connected": True},
		"devices": {
			"led_status": False,
			"neo_led_status": False,
			"ws2812_status": False,
			"relay_status": False,
			"mini_fan_status": False,
		},
	}

	decision = policy.evaluate(proposal, capability, state)
	assert decision.decision == "ask", decision
	assert decision.reason == "broad_all_devices_scope_requires_confirmation", decision

	confirmed = proposal.model_copy(
		update={"arguments": {**proposal.arguments, "_confirmed": True}}
	)
	decision = policy.evaluate(confirmed, capability, state)
	assert decision.decision == "allow", decision


def test_command_is_not_verified_without_readback() -> None:
	tool_runner_module.DEVICE_VERIFICATION_TIMEOUT_SECONDS = 0
	tool_runner_module.DEVICE_VERIFICATION_POLL_SECONDS = 0
	mqtt = FakeMQTT()
	runner = ToolRunner(
		CapabilityRegistry(),
		DeviceExecutor(mqtt),
		policy_engine=PolicyEngine(),
	)
	proposal = build_tool_proposal(
		{"action": "turn_on", "target": "main_led", "confidence": 1.0}
	)
	assert proposal is not None

	result = runner.run(proposal)
	assert mqtt.published == [("setValueLedBlinky", True)]
	assert mqtt.sensor_state["devices"]["led_status"] is False
	assert result.status == "state_changed", result
	assert result.verification.status == "timeout", result.verification


def test_static_thresholds_are_reported_even_with_low_ml_score() -> None:
	classification = classify_anomaly(
		{
			"sensors": {
				"temperature": 21.2,
				"humidity": 55.4,
				"anomaly": 0.0,
			}
		},
		{"is_stale": False},
	)

	assert classification["type"] != "normal", classification
	assert classification["severity"] == "low", classification
	assert "below" in classification["detail"], classification


async def main() -> None:
	await test_device_semantics()
	await test_target_resolution_from_clarification()
	await test_fast_confirmation_and_direct_device_rendering()
	await test_device_clarification_payload_is_serializable()
	await test_fast_device_intent_routing()
	await test_fast_read_only_routing_and_rendering()
	await test_identity_questions_do_not_use_router_direct_response()
	await test_answer_previous_followup_uses_conversation_context()
	await test_fast_device_pipeline_skips_memory_and_parser_llm()
	await test_simple_general_pipeline_skips_memory_retrieval()
	await test_action_memory_question_is_not_device_control()
	await test_conditional_device_request_checks_sensor_before_acting()
	await test_temporal_condition_checks_telemetry_window_before_acting()
	await test_temporal_conditional_device_request_bypasses_bad_router()
	await test_conditional_noop_response_stays_vietnamese()
	await test_conditional_command_prefers_explicit_target_over_recent_actions()
	await test_multi_action_keeps_condition_scoped_per_action()
	await test_short_device_followups_use_conversation_focus()
	await test_web_search_pipeline_uses_search_service()
	await test_weather_web_query_is_grounded_with_date_and_location()
	test_specialized_intent_classifier_supports_vietnamese_and_english()
	await test_web_research_uses_specialized_weather_service()
	await test_web_research_falls_back_when_specialized_unavailable()
	test_duckduckgo_web_search_service_disabled_without_network()
	test_all_devices_confirmation_policy()
	test_command_is_not_verified_without_readback()
	test_static_thresholds_are_reported_even_with_low_ml_score()
	print("device behavior checks passed")


if __name__ == "__main__":
	asyncio.run(main())
