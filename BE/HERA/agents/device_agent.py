"""
Device Control Agent
====================
Parses actuator requests and returns tool proposals.
The orchestrator invokes the central ToolRunner for side effects.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from config import NORMAL_HUMI_MAX, NORMAL_HUMI_MIN, NORMAL_TEMP_MAX, NORMAL_TEMP_MIN
from core.llm_service import LLMService
from core.message import AgentResponse, UserMessage
from core.runtime_settings import runtime_settings
from domain.devices import DEVICE_TARGETS
from prompts import (
	DEVICE_COMMAND_INTERPRETER_PROMPT,
	DEVICE_TARGET_CLARIFICATION_PROMPT,
)
from runtime import ToolRunner
from schemas import SpecialistReport, ToolProposal

from agents.base import AgentBase
from core.logger import log_agent

DEVICE_LABEL_TARGETS = {
	"Main LED": "main_led",
	"NeoPixel LED": "neo_led",
	"WS2812 LED": "ws2812",
	"Relay": "relay",
	"Mini fan": "mini_fan",
}

ACTION_STOPWORDS = {
	"bat",
	"bật",
	"tat",
	"tắt",
	"mo",
	"mở",
	"dong",
	"đóng",
	"turn",
	"switch",
	"status",
	"trạng",
	"trang",
	"thái",
	"thai",
	"on",
	"off",
}

FILLER_TOKENS = {
	"toi",
	"tôi",
	"giup",
	"giúp",
	"gium",
	"giùm",
	"cho",
	"hay",
	"hãy",
	"xin",
	"vui",
	"lòng",
	"long",
	"di",
	"đi",
	"nhe",
	"nhé",
	"nha",
	"len",
	"lên",
	"voi",
	"với",
	"nao",
	"nào",
	"cac",
	"các",
	"nhung",
	"những",
	"cai",
	"cái",
	"the",
	"dang",
	"đang",
	"hien",
	"hiện",
	"tai",
	"tại",
	"la",
	"là",
	"thi",
	"thì",
	"sao",
	"phòng",
	"phong",
	"khách",
	"khach",
	"ngủ",
	"ngu",
	"bếp",
	"bep",
}

RECENT_REFERENCE_TOKENS = {
	"vua",
	"vừa",
	"duoc",
	"được",
	"recently",
	"just",
	"changed",
}

GENERIC_LIGHT_TOKEN_SETS = {
	frozenset({"đèn"}),
	frozenset({"den"}),
	frozenset({"led"}),
	frozenset({"đèn", "led"}),
	frozenset({"den", "led"}),
	frozenset({"bóng", "đèn"}),
	frozenset({"bong", "den"}),
	frozenset({"lamp"}),
	frozenset({"lamps"}),
	frozenset({"light"}),
	frozenset({"lights"}),
	frozenset({"lighting"}),
}

GENERIC_DEVICE_TOKEN_SETS = {
	frozenset({"thiết", "bị"}),
	frozenset({"thiet", "bi"}),
	frozenset({"device"}),
	frozenset({"devices"}),
}

ALL_LIGHTS_TOKEN_SETS = {
	frozenset({"tất", "cả", "đèn"}),
	frozenset({"tat", "ca", "den"}),
	frozenset({"all", "lights"}),
}

ALL_DEVICES_TOKEN_SETS = {
	frozenset({"tất", "cả", "thiết", "bị"}),
	frozenset({"tat", "ca", "thiet", "bi"}),
	frozenset({"all", "devices"}),
}

STATUS_MARKERS = (
	"trạng thái",
	"trang thai",
	"bật hay tắt",
	"bat hay tat",
	"tắt hay bật",
	"tat hay bat",
	"on hay off",
	"status",
)

CONDITIONAL_MARKERS = (
	"nếu",
	"neu",
	"if",
	"khi",
	"when",
	"trường hợp",
	"truong hop",
)

LIGHT_LANGUAGE_TOKENS = {
	"đèn",
	"den",
	"led",
	"bóng",
	"bong",
	"lamp",
	"lamps",
	"light",
	"lights",
	"lighting",
}

GENERIC_DEVICE_LANGUAGE_TOKENS = {
	"thiết",
	"thiet",
	"bị",
	"bi",
	"device",
	"devices",
}

OTHER_DEVICE_MARKERS = (
	"thiết bị khác",
	"thiet bi khac",
	"các thiết bị khác",
	"cac thiet bi khac",
	"những thiết bị khác",
	"nhung thiet bi khac",
	"other devices",
)

TURN_ON_MARKERS = (
	"bật",
	"bat",
	"mở",
	"mo",
	"turn on",
	"switch on",
)

TURN_OFF_MARKERS = (
	"tắt",
	"tat",
	"đóng",
	"dong",
	"turn off",
	"switch off",
)

RECENT_REFERENCE_MARKERS = (
	"vừa được bật",
	"vua duoc bat",
	"vừa bật",
	"vua bat",
	"vừa được tắt",
	"vua duoc tat",
	"vừa tắt",
	"vua tat",
	"recently changed",
)

SPECIFIC_TARGET_TOKEN_SETS: dict[frozenset[str], str] = {
	frozenset({"main", "led"}): "main_led",
	frozenset({"đèn", "chính"}): "main_led",
	frozenset({"den", "chinh"}): "main_led",
	frozenset({"neo", "led"}): "neo_led",
	frozenset({"neo"}): "neo_led",
	frozenset({"neopixel", "led"}): "neo_led",
	frozenset({"neopixel"}): "neo_led",
	frozenset({"ws2812"}): "ws2812",
	frozenset({"ws2812", "led"}): "ws2812",
	frozenset({"relay"}): "relay",
	frozenset({"mini", "fan"}): "mini_fan",
	frozenset({"fan"}): "mini_fan",
	frozenset({"quạt"}): "mini_fan",
	frozenset({"quat"}): "mini_fan",
}

SENSOR_CONDITION_ALIASES = {
	"temperature": (
		"nhiệt độ",
		"nhiet do",
		"temperature",
		"temp",
	),
	"humidity": (
		"độ ẩm",
		"do am",
		"humidity",
	),
	"light": (
		"ánh sáng",
		"anh sang",
		"light",
	),
	"anomaly": (
		"bất thường",
		"bat thuong",
		"anomaly",
	),
}

SENSOR_LABELS_VI = {
	"temperature": "nhiệt độ",
	"humidity": "độ ẩm",
	"light": "ánh sáng",
	"anomaly": "điểm bất thường",
}

SENSOR_UNITS = {
	"temperature": "°C",
	"humidity": "%",
	"light": "",
	"anomaly": "",
}


def extract_json_object(raw_text: str | None) -> dict:
	text = (raw_text or "").strip()
	if not text:
		return {}

	if text.startswith("```"):
		text = text.strip("`")
		if "\n" in text:
			text = text.split("\n", 1)[1]

	start = text.find("{")
	end = text.rfind("}")
	if start == -1 or end == -1 or end <= start:
		return {}

	try:
		parsed = json.loads(text[start : end + 1])
	except json.JSONDecodeError:
		return {}
	return parsed if isinstance(parsed, dict) else {}


def normalize_text(text: str) -> str:
	return " ".join(text.strip().lower().split())


def tokenize_text(text: str) -> set[str]:
	return {
		token
		for token in re.findall(r"[0-9A-Za-zÀ-ỹđĐ]+", normalize_text(text))
		if token
	}


def has_light_language(tokens: set[str]) -> bool:
	return bool(tokens & LIGHT_LANGUAGE_TOKENS)


def has_generic_device_language(tokens: set[str]) -> bool:
	return bool(tokens & GENERIC_DEVICE_LANGUAGE_TOKENS)


def needs_recent_action_memory(text: str) -> bool:
	normalized = normalize_text(text)
	tokens = tokenize_text(text)
	return any(marker in normalized for marker in RECENT_REFERENCE_MARKERS) or bool(
		tokens & RECENT_REFERENCE_TOKENS
	)


def has_conditional_language(text: str) -> bool:
	normalized = normalize_text(text)
	return any(marker in normalized for marker in CONDITIONAL_MARKERS)


def should_use_local_fast_path(text: str) -> bool:
	return not has_conditional_language(text)


def detect_action(normalized: str) -> str | None:
	if any(marker in normalized for marker in STATUS_MARKERS):
		return "status"
	if any(marker in normalized for marker in TURN_OFF_MARKERS):
		return "turn_off"
	if any(marker in normalized for marker in TURN_ON_MARKERS):
		return "turn_on"
	return None


def detect_leading_action(normalized: str) -> str | None:
	patterns = (
		(
			"turn_on",
			r"^(?:xin\s+)?(?:hãy\s+|hay\s+)?(?:giúp\s+tôi\s+|giup\s+toi\s+)?(?:cho\s+tôi\s+|cho\s+toi\s+)?(?:vui\s+lòng\s+|vui\s+long\s+)?(?:bật|bat|mở|mo|turn on|switch on)\b",
		),
		(
			"turn_off",
			r"^(?:xin\s+)?(?:hãy\s+|hay\s+)?(?:giúp\s+tôi\s+|giup\s+toi\s+)?(?:cho\s+tôi\s+|cho\s+toi\s+)?(?:vui\s+lòng\s+|vui\s+long\s+)?(?:tắt|tat|đóng|dong|turn off|switch off)\b",
		),
		(
			"status",
			r"^(?:xin\s+)?(?:hãy\s+|hay\s+)?(?:cho\s+tôi\s+|cho\s+toi\s+)?(?:xem|kiểm tra|kiem tra|check)\b",
		),
	)
	for action, pattern in patterns:
		if re.search(pattern, normalized):
			return action
	return None


def fast_parse_local_command(text: str) -> dict[str, Any] | None:
	normalized = normalize_text(text)

	# ── Status-question detection (must come BEFORE action detection) ──
	# Patterns like "bật chưa", "đã bật", "tắt chưa", "đang tắt" are
	# inquiries about state, not commands to change state.
	status_question_patterns = (
		r"(?:đã|da)\s+(?:được\s+)?(?:bật|bat|tắt|tat|mở|mo|đóng|dong)",
		r"(?:được|duoc)\s+(?:bật|bat|tắt|tat|mở|mo|đóng|dong)",
		r"(?:đang|dang)\s+(?:bật|bat|tắt|tat|mở|mo|đóng|dong|chạy|chay|hoạt động|hoat dong)",
		r"(?:bật|bat|tắt|tat|mở|mo|đóng|dong)\s+(?:chưa|chua|chưa\b|không|khong|rồi|roi)",
		r"(?:bật|bat|tắt|tat)\s+hay\s+(?:tắt|tat|bật|bat)",
		r"(?:có|co)\s+(?:đang|dang)\s+(?:bật|bat|tắt|tat|chạy|chay)",
	)
	question_particles = (
		"chưa",
		"chua",
		"không",
		"khong",
		"nhỉ",
		"nhi",
		"hả",
		"ha",
		"?",
	)
	has_question = any(q in normalized for q in question_particles)
	is_status_question = has_question and any(
		re.search(p, normalized) for p in status_question_patterns
	)

	if is_status_question:
		# Force action=status, skip normal action detection
		action = "status"
		leading_action = "status"
	else:
		action = detect_action(normalized)
		leading_action = detect_leading_action(normalized)
		if (
			has_conditional_language(normalized)
			and action in {"turn_on", "turn_off"}
			and leading_action == "status"
		):
			pass
		elif leading_action is not None:
			action = leading_action
		elif re.search(r"^(?:ắt|at)\b", normalized):
			action = "turn_off"
			leading_action = action

	if action is None:
		return None

	tokens = tokenize_text(text)
	if not tokens:
		return None

	has_recent_reference = any(
		marker in normalized for marker in RECENT_REFERENCE_MARKERS
	)
	has_light = has_light_language(tokens)
	has_generic_device = has_generic_device_language(tokens)
	has_device_language = (
		has_light
		or has_generic_device
		or any(token in tokens for token in ("relay", "ws2812", "fan", "quạt", "quat"))
	)
	if has_recent_reference and has_device_language and leading_action == action:
		return {
			"action": action,
			"target": None,
			"reference": "recent_changed_devices",
			"confidence": 0.9,
		}

	significant_tokens = {
		token
		for token in tokens
		if token not in ACTION_STOPWORDS
		and token not in FILLER_TOKENS
		and token not in RECENT_REFERENCE_TOKENS
	}
	if not significant_tokens:
		return None

	significant = frozenset(significant_tokens)
	if has_light and any(marker in normalized for marker in OTHER_DEVICE_MARKERS):
		return {
			"action": action,
			"target": "all_devices",
			"reference": "none",
			"confidence": 0.85,
		}
	target = None
	for token_set, candidate in sorted(
		SPECIFIC_TARGET_TOKEN_SETS.items(),
		key=lambda item: len(item[0]),
		reverse=True,
	):
		if token_set.issubset(significant):
			target = candidate
			break
	if target is not None:
		return {
			"action": action,
			"target": target,
			"reference": "none",
			"confidence": 0.98,
		}
	if significant in ALL_LIGHTS_TOKEN_SETS:
		return {
			"action": action,
			"target": "all_lights",
			"reference": "none",
			"confidence": 0.95,
		}
	if significant in ALL_DEVICES_TOKEN_SETS:
		return {
			"action": action,
			"target": "all_devices",
			"reference": "none",
			"confidence": 0.95,
		}
	if significant in GENERIC_LIGHT_TOKEN_SETS:
		return {
			"action": action,
			"target": "all_lights",
			"reference": "none",
			"confidence": 0.9,
		}
	if has_light:
		return {
			"action": action,
			"target": "all_lights",
			"reference": "none",
			"confidence": 0.82,
		}
	if significant in GENERIC_DEVICE_TOKEN_SETS:
		return {
			"action": action,
			"target": None,
			"reference": "none",
			"confidence": 0.85,
		}
	if has_generic_device:
		return {
			"action": action,
			"target": None,
			"reference": "none",
			"confidence": 0.75,
		}
	return None


def fast_resolve_target_text(text: str) -> dict[str, Any] | None:
	normalized = normalize_text(text)
	tokens = tokenize_text(text)
	if not tokens:
		return None
	significant_tokens = {
		token
		for token in tokens
		if token not in ACTION_STOPWORDS
		and token not in FILLER_TOKENS
		and token not in RECENT_REFERENCE_TOKENS
	}
	significant = frozenset(significant_tokens)
	for token_set, candidate in sorted(
		SPECIFIC_TARGET_TOKEN_SETS.items(),
		key=lambda item: len(item[0]),
		reverse=True,
	):
		if token_set.issubset(significant):
			return {"target": candidate, "confidence": 0.98}
	if significant in ALL_LIGHTS_TOKEN_SETS or (
		has_light_language(tokens) and "tất cả" in normalized
	):
		return {"target": "all_lights", "confidence": 0.95}
	if significant in ALL_DEVICES_TOKEN_SETS or any(
		marker in normalized for marker in OTHER_DEVICE_MARKERS
	):
		return {"target": "all_devices", "confidence": 0.9}
	if significant in GENERIC_LIGHT_TOKEN_SETS or has_light_language(tokens):
		return {"target": "all_lights", "confidence": 0.82}
	return None


def build_sensor_condition(
	text: str,
	sensor_snapshot: dict | None,
	raw_condition: dict | None = None,
) -> dict | None:
	normalized = normalize_text(text)
	if raw_condition is not None:
		return evaluate_sensor_condition(raw_condition, sensor_snapshot)
	if not has_conditional_language(normalized):
		return None

	sensor_name = detect_condition_sensor(normalized)
	if sensor_name is None:
		return {
			"type": "sensor_threshold",
			"status": "unknown",
			"reason": "missing_sensor_reference",
		}

	operator, threshold = detect_condition_operator_threshold(normalized, sensor_name)
	if operator is None or threshold is None:
		return {
			"type": "sensor_threshold",
			"status": "unknown",
			"sensor": sensor_name,
			"sensor_label": SENSOR_LABELS_VI.get(sensor_name, sensor_name),
			"reason": "missing_comparison_threshold",
		}

	return evaluate_sensor_condition(
		{
			"type": "sensor_threshold",
			"sensor": sensor_name,
			"operator": operator,
			"threshold": threshold,
		},
		sensor_snapshot,
	)


def evaluate_sensor_condition(
	raw_condition: dict,
	sensor_snapshot: dict | None,
) -> dict | None:
	if raw_condition.get("type") not in {None, "sensor_threshold"}:
		return {
			"type": str(raw_condition.get("type") or "unknown"),
			"status": "unknown",
			"reason": "unsupported_condition_type",
		}

	sensor_name = raw_condition.get("sensor")
	if sensor_name not in SENSOR_CONDITION_ALIASES:
		return {
			"type": "sensor_threshold",
			"status": "unknown",
			"reason": "missing_or_invalid_sensor",
		}

	operator = raw_condition.get("operator")
	if operator not in {">", ">=", "<", "<="}:
		return {
			"type": "sensor_threshold",
			"status": "unknown",
			"sensor": sensor_name,
			"sensor_label": SENSOR_LABELS_VI.get(sensor_name, sensor_name),
			"reason": "missing_or_invalid_operator",
		}

	try:
		threshold = float(raw_condition.get("threshold"))
	except TypeError, ValueError:
		return {
			"type": "sensor_threshold",
			"status": "unknown",
			"sensor": sensor_name,
			"sensor_label": SENSOR_LABELS_VI.get(sensor_name, sensor_name),
			"operator": operator,
			"reason": "missing_or_invalid_threshold",
		}

	sensors = {}
	if isinstance(sensor_snapshot, dict):
		raw_sensors = sensor_snapshot.get("sensors", {})
		if isinstance(raw_sensors, dict):
			sensors = raw_sensors
	current_value = sensors.get(sensor_name)
	condition = {
		"type": "sensor_threshold",
		"status": "unknown",
		"sensor": sensor_name,
		"sensor_label": SENSOR_LABELS_VI.get(sensor_name, sensor_name),
		"unit": SENSOR_UNITS.get(sensor_name, ""),
		"operator": operator,
		"threshold": threshold,
		"current_value": current_value,
		"source": "current_sensor_snapshot",
	}
	if not isinstance(current_value, int | float):
		condition["reason"] = "missing_current_sensor_value"
		return condition

	met = compare_numeric(float(current_value), operator, float(threshold))
	condition["met"] = met
	condition["status"] = "met" if met else "not_met"
	return condition


def detect_condition_sensor(normalized: str) -> str | None:
	for sensor_name, aliases in SENSOR_CONDITION_ALIASES.items():
		if any(alias in normalized for alias in aliases):
			return sensor_name
	return None


def detect_condition_operator_threshold(
	normalized: str,
	sensor_name: str,
) -> tuple[str | None, float | None]:
	operator_patterns: tuple[tuple[str, tuple[str, ...]], ...] = (
		(">=", (r">=\s*", r"ít nhất\s+", r"it nhat\s+", r"từ\s+", r"tu\s+")),
		("<=", (r"<=\s*", r"tối đa\s+", r"toi da\s+")),
		(
			">",
			(
				r">\s*",
				r"trên\s+",
				r"tren\s+",
				r"cao hơn\s+",
				r"cao hon\s+",
				r"lớn hơn\s+",
				r"lon hon\s+",
				r"hơn\s+",
				r"hon\s+",
			),
		),
		(
			"<",
			(
				r"<\s*",
				r"dưới\s+",
				r"duoi\s+",
				r"thấp hơn\s+",
				r"thap hon\s+",
				r"nhỏ hơn\s+",
				r"nho hon\s+",
			),
		),
	)
	for operator, prefixes in operator_patterns:
		for prefix in prefixes:
			match = re.search(prefix + r"(-?\d+(?:[.,]\d+)?)", normalized)
			if match:
				return operator, float(match.group(1).replace(",", "."))

	if sensor_name == "temperature":
		if any(marker in normalized for marker in ("cao", "nóng", "nong", "high")):
			return ">", float(NORMAL_TEMP_MAX)
		if any(
			marker in normalized for marker in ("thấp", "thap", "lạnh", "lanh", "low")
		):
			return "<", float(NORMAL_TEMP_MIN)
	if sensor_name == "humidity":
		if any(marker in normalized for marker in ("cao", "ẩm", "am", "high")):
			return ">", float(NORMAL_HUMI_MAX)
		if any(
			marker in normalized for marker in ("thấp", "thap", "khô", "kho", "low")
		):
			return "<", float(NORMAL_HUMI_MIN)
	return None, None


def compare_numeric(value: float, operator: str, threshold: float) -> bool:
	if operator == ">":
		return value > threshold
	if operator == ">=":
		return value >= threshold
	if operator == "<":
		return value < threshold
	if operator == "<=":
		return value <= threshold
	return False


def target_from_recent_changed_devices(recent_actions: list) -> str | None:
	for action in reversed(recent_actions):
		if not isinstance(action, dict):
			continue
		changed = action.get("changed_entities")
		if not isinstance(changed, list) or not changed:
			continue
		targets = {DEVICE_LABEL_TARGETS.get(str(entity)) for entity in changed}
		targets.discard(None)
		if not targets:
			continue
		if targets == {"main_led", "neo_led", "ws2812", "relay", "mini_fan"}:
			return "all_devices"
		if targets == {"main_led", "neo_led", "ws2812"}:
			return "all_lights"
		if len(targets) == 1:
			return next(iter(targets))
		return None
	return None


def normalise_command(
	parsed: dict[str, Any],
	recent_actions: list | None = None,
) -> dict:
	action = parsed.get("action")
	target = parsed.get("target")
	reference = parsed.get("reference")
	requested_action = parsed.get("requested_action")
	requested_target = parsed.get("requested_target")
	condition = parsed.get("condition")
	if action not in {"turn_on", "turn_off", "status", "unknown"}:
		action = "unknown"
	if reference not in {"none", "recent_changed_devices"}:
		reference = "none"
	if reference == "recent_changed_devices":
		target = target_from_recent_changed_devices(recent_actions or [])
	if target not in DEVICE_TARGETS:
		target = None
	if action == "unknown":
		target = None
	if requested_action not in {"turn_on", "turn_off", "status"}:
		requested_action = (
			action if action in {"turn_on", "turn_off", "status"} else None
		)
	if requested_target not in DEVICE_TARGETS:
		requested_target = target
	command = {
		"action": action,
		"target": target,
		"reference": reference,
		"confidence": parsed.get("confidence"),
		"requested_action": requested_action,
		"requested_target": requested_target,
	}
	if isinstance(condition, dict):
		command["condition"] = condition
	return command


def capability_from_action(action: str) -> str | None:
	return {
		"turn_on": "turn_on_device",
		"turn_off": "turn_off_device",
		"status": "get_device_status",
	}.get(action)


def build_tool_proposal(command: dict[str, Any]) -> ToolProposal | None:
	condition = command.get("condition")
	if isinstance(condition, dict) and condition.get("status") != "met":
		return None

	capability_name = capability_from_action(command["action"])
	if capability_name is None:
		return None

	target = command.get("target")
	if target is None:
		return None
	confidence = command.get("confidence")
	if not isinstance(confidence, int | float):
		confidence = 0.0 if target is None else 0.6

	arguments = (
		{"device_target": target} if capability_name != "get_device_status" else {}
	)
	if capability_name == "get_device_status":
		arguments = {"device_target": target}

	return ToolProposal(
		capability_name=capability_name,
		arguments=arguments,
		rationale=(
			"Parsed user request into a device capability. "
			"Execution must go through the central ToolRunner."
		),
		expected_outcome=(
			"Device state changes if requested state differs from current state."
			if capability_name != "get_device_status"
			else "Current device state is reported without changing hardware."
		),
		confidence=max(0.0, min(float(confidence), 1.0)),
		ambiguity_detected=False,
		clarification_question=None,
	)


class DeviceControlAgent(AgentBase):
	def __init__(
		self,
		llm: LLMService,
		tool_runner: ToolRunner,
	) -> None:
		self.llm = llm
		self.tool_runner = tool_runner

	@property
	def name(self) -> str:
		return "device_control"

	@property
	def description(self) -> str:
		return "Controls LEDs and actuators on the ESP32 device."

	async def parse_command(self, message: UserMessage, context: dict) -> dict:
		model_override = runtime_settings.get_active_model("deviceControlModel")
		raw_memory_context = context.get("memory_context", {})
		if not isinstance(raw_memory_context, dict):
			raw_memory_context = {}
		device_memory_context = {
			"recent_actions": raw_memory_context.get("recent_actions", []),
			"user_profile": raw_memory_context.get("user_profile", {}),
		}
		sensor_snapshot = context.get("sensor_snapshot", {})
		fast_parsed = (
			fast_parse_local_command(message.text)
			if should_use_local_fast_path(message.text)
			else None
		)
		if fast_parsed is not None:
			command = normalise_command(
				fast_parsed,
				device_memory_context.get("recent_actions", []),
			)
			raw_condition = command.get("condition")
			condition = build_sensor_condition(
				message.text,
				sensor_snapshot,
				raw_condition if isinstance(raw_condition, dict) else None,
			)
			if condition is not None:
				command["condition"] = condition
			return command
		device_context = json.dumps(
			self.tool_runner.get_device_status_report(),
			indent=2,
		)
		memory_context = json.dumps(
			device_memory_context,
			ensure_ascii=False,
			indent=2,
		)
		messages = [
			{
				"role": "system",
				"content": (
					DEVICE_COMMAND_INTERPRETER_PROMPT
					+ "\n\nCurrent device snapshot:\n"
					+ device_context
					+ "\n\nRecent action memory:\n"
					+ memory_context
				),
			},
			{"role": "user", "content": message.text},
		]
		result = await asyncio.to_thread(
			self.llm.completion,
			messages,
			None,
			model_override,
		)
		parsed = extract_json_object(result["content"])
		command = normalise_command(
			parsed,
			device_memory_context.get("recent_actions", []),
		)
		raw_condition = command.get("condition")
		condition = build_sensor_condition(
			message.text,
			sensor_snapshot,
			raw_condition if isinstance(raw_condition, dict) else None,
		)
		if condition is not None:
			command["condition"] = condition
		return command

	async def resolve_target_from_clarification(
		self,
		message: UserMessage,
		*,
		requested_action: str,
	) -> dict[str, Any]:
		fast_resolved = fast_resolve_target_text(message.text)
		if fast_resolved is not None:
			return fast_resolved
		model_override = runtime_settings.get_active_model("deviceControlModel")
		messages = [
			{
				"role": "system",
				"content": (
					DEVICE_TARGET_CLARIFICATION_PROMPT
					+ f"\n\nRequested action:\n{requested_action}"
				),
			},
			{"role": "user", "content": message.text},
		]
		result = await asyncio.to_thread(
			self.llm.completion,
			messages,
			None,
			model_override,
		)
		parsed = extract_json_object(result["content"])
		target = parsed.get("target")
		if target not in DEVICE_TARGETS:
			target = None
		confidence = parsed.get("confidence")
		if not isinstance(confidence, int | float):
			confidence = 0.0 if target is None else 0.6
		return {
			"target": target,
			"confidence": max(0.0, min(float(confidence), 1.0)),
		}

	@staticmethod
	def target_from_recent_changed_devices(recent_actions: list) -> str | None:
		return target_from_recent_changed_devices(recent_actions)

	async def process(
		self,
		message: UserMessage,
		context: dict,
	) -> AgentResponse:
		command = await self.parse_command(message, context)
		tool_proposal = build_tool_proposal(command)
		condition = command.get("condition")
		condition_str = (
			f" condition={condition.get('status', '?')}"
			if isinstance(condition, dict)
			else ""
		)
		log_agent(
			f"DeviceControl: {command['action']} → {command['target']}",
			data={
				"confidence": command.get("confidence"),
				"reference": command.get("reference"),
				"has_proposal": tool_proposal is not None,
			},
			detail=(
				f"proposal={tool_proposal.capability_name}"
				if tool_proposal
				else f"no proposal{condition_str}"
			),
		)

		clarification_question = None
		summary = "unknown_or_ambiguous_command"
		condition = command.get("condition")
		if isinstance(condition, dict) and condition.get("status") == "not_met":
			summary = "condition_not_met"
		elif isinstance(condition, dict) and condition.get("status") == "unknown":
			summary = "condition_unknown"
		elif (
			isinstance(condition, dict)
			and condition.get("status") == "met"
			and tool_proposal
		):
			summary = "condition_met_tool_proposal_ready"
		elif (
			command["action"] in {"turn_on", "turn_off", "status"}
			and command["target"] is None
		):
			summary = "awaiting_target_clarification"
			clarification_question = "Which device should I control?"
		elif tool_proposal:
			summary = "tool_proposal_ready"

		report = {
			"parsed_command": command,
			"tool_proposals": (
				[tool_proposal.model_dump(mode="json")] if tool_proposal else []
			),
			"device_status": self.tool_runner.get_device_status_report(),
		}
		analysis_payload = dict(report)
		specialist_report = SpecialistReport(
			specialist_name=self.name,
			summary=summary,
			tool_proposals=[tool_proposal] if tool_proposal else [],
			clarification_question=clarification_question,
			analysis_payload=analysis_payload,
		)
		report["specialist_report"] = specialist_report.model_dump(mode="json")

		return AgentResponse(
			text=json.dumps(report, ensure_ascii=False),
			agent_name=self.name,
			tools_used=[],
			metadata=report,
		)
