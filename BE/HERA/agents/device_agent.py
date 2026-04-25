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
from core.logger import log_agent
from core.message import AgentResponse, UserMessage
from core.runtime_settings import runtime_settings
from domain.devices import DEVICE_TARGETS
from prompts import (
	DEVICE_COMMAND_INTERPRETER_PROMPT,
	DEVICE_TARGET_CLARIFICATION_PROMPT,
)
from runtime import (
	ToolRunner,
	get_current_telemetry_call,
	get_device_status_call,
	get_telemetry_window_call,
	set_device_state_call,
)
from schemas import SpecialistReport, ToolProposal

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
	# frozenset({"led"}),  # Removed: "led" now defaults to main_led in SPECIFIC_TARGET_TOKEN_SETS
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
	frozenset({"toàn", "bộ", "đèn"}),
	frozenset({"toan", "bo", "den"}),
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

STATUS_FOLLOWUP_MARKERS = (
	"chắc chưa",
	"chac chua",
	"đúng chưa",
	"dung chua",
	"đúng không",
	"dung khong",
	"chưa",
	"chua",
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
	frozenset({"led"}): "main_led",
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

TELEMETRY_SUMMARY_FIELDS = {
	"temperature": "temperature_c",
	"humidity": "humidity_percent",
	"light": "light",
	"anomaly": "anomaly_score",
}

WINDOW_CONDITION_TYPES = {
	"sensor_window_threshold",
	"temporal_sensor_threshold",
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
	if detect_condition_window_seconds(normalized) is not None:
		return False
	tokens = tokenize_text(text)
	return any(marker in normalized for marker in RECENT_REFERENCE_MARKERS) or bool(
		tokens & RECENT_REFERENCE_TOKENS
	)


def has_conditional_language(text: str) -> bool:
	normalized = normalize_text(text)
	return any(marker in normalized for marker in CONDITIONAL_MARKERS)


def should_use_local_fast_path(text: str) -> bool:
	return not has_conditional_language(text)


def looks_like_standalone_device_request(text: str) -> bool:
	"""True when a pending clarification should give way to a full new request."""
	parsed = fast_parse_local_command(text)
	return (
		isinstance(parsed, dict)
		and parsed.get("action") in {"turn_on", "turn_off", "status"}
		and parsed.get("target") is not None
		and not has_conditional_language(text)
	)


def looks_like_contextual_device_request(text: str, focus_target: str | None) -> bool:
	"""True when a short follow-up can use the active device focus."""
	return fast_parse_contextual_command(text, focus_target) is not None


def looks_like_conditional_device_request(
	text: str,
	focus_target: str | None = None,
) -> bool:
	"""True when a conditional sentence contains a concrete actuator request."""
	if not has_conditional_language(text):
		return False
	parsed = fast_parse_local_command(text)
	if parsed is None:
		parsed = fast_parse_contextual_command(text, focus_target)
	if not isinstance(parsed, dict):
		return False
	return parsed.get("action") in {"turn_on", "turn_off", "status"}


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
			"target": None,
			"reference": "none",
			"confidence": 0.9,
		}
	if has_light:
		return {
			"action": action,
			"target": None,
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


def explicit_target_from_text(text: str) -> str | None:
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
			return candidate
	if significant in ALL_DEVICES_TOKEN_SETS:
		return "all_devices"
	if significant in ALL_LIGHTS_TOKEN_SETS:
		return "all_lights"
	return None


def detect_contextual_action(text: str) -> str | None:
	normalized = normalize_text(text)
	action = detect_action(normalized)
	leading_action = detect_leading_action(normalized)
	if leading_action in {"turn_on", "turn_off"}:
		return leading_action
	if action in {"turn_on", "turn_off", "status"}:
		return action
	if any(marker in normalized for marker in STATUS_FOLLOWUP_MARKERS):
		return "status"
	return None


def fast_parse_contextual_command(
	text: str,
	focus_target: str | None,
) -> dict[str, Any] | None:
	if focus_target not in DEVICE_TARGETS:
		return None
	if explicit_target_from_text(text) is not None:
		return None
	action = detect_contextual_action(text)
	if action not in {"turn_on", "turn_off", "status"}:
		return None
	return {
		"action": action,
		"target": focus_target,
		"reference": "discourse_focus",
		"confidence": 0.88,
	}


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
		return {"target": None, "confidence": 0.82}
	return None


def build_sensor_condition(
	text: str,
	sensor_snapshot: dict | None,
	raw_condition: dict | None = None,
	*,
	telemetry_store: Any | None = None,
	user_id: str | None = None,
) -> dict | None:
	normalized = normalize_text(text)
	window_seconds = detect_condition_window_seconds(normalized)
	if raw_condition is not None:
		condition_type = raw_condition.get("type")
		if (
			condition_type in WINDOW_CONDITION_TYPES
			or raw_condition.get("window_seconds") is not None
			or window_seconds is not None
		):
			window_condition = dict(raw_condition)
			window_condition["type"] = "sensor_window_threshold"
			if window_condition.get("window_seconds") is None:
				window_condition["window_seconds"] = window_seconds
			return evaluate_sensor_window_condition(
				window_condition,
				telemetry_store=telemetry_store,
				user_id=user_id,
			)
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

	condition_payload = {
		"type": "sensor_threshold",
		"sensor": sensor_name,
		"operator": operator,
		"threshold": threshold,
	}
	if window_seconds is not None:
		condition_payload["type"] = "sensor_window_threshold"
		condition_payload["window_seconds"] = window_seconds
		return evaluate_sensor_window_condition(
			condition_payload,
			telemetry_store=telemetry_store,
			user_id=user_id,
		)
	return evaluate_sensor_condition(condition_payload, sensor_snapshot)


class DeviceConditionEvaluator:
	"""Ground conditional device commands against sensor and telemetry facts."""

	def __init__(self, telemetry_store: Any | None = None) -> None:
		self.telemetry_store = telemetry_store

	def evaluate(
		self,
		command: dict[str, Any],
		*,
		user_text: str,
		sensor_snapshot: dict | None,
		user_id: str | None,
	) -> dict[str, Any]:
		raw_condition = command.get("condition")
		condition = build_sensor_condition(
			user_text,
			sensor_snapshot,
			raw_condition if isinstance(raw_condition, dict) else None,
			telemetry_store=self.telemetry_store,
			user_id=user_id,
		)
		if condition is None:
			return command
		return {**command, "condition": condition}


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
	if not isinstance(current_value, (int, float)):
		condition["reason"] = "missing_current_sensor_value"
		return condition

	met = compare_numeric(float(current_value), operator, float(threshold))
	condition["met"] = met
	condition["status"] = "met" if met else "not_met"
	return condition


def evaluate_sensor_window_condition(
	raw_condition: dict,
	*,
	telemetry_store: Any | None,
	user_id: str | None,
) -> dict | None:
	sensor_name = raw_condition.get("sensor")
	if sensor_name not in SENSOR_CONDITION_ALIASES:
		return {
			"type": "sensor_window_threshold",
			"status": "unknown",
			"reason": "missing_or_invalid_sensor",
		}

	operator = raw_condition.get("operator")
	if operator not in {">", ">=", "<", "<="}:
		return {
			"type": "sensor_window_threshold",
			"status": "unknown",
			"sensor": sensor_name,
			"sensor_label": SENSOR_LABELS_VI.get(sensor_name, sensor_name),
			"reason": "missing_or_invalid_operator",
		}

	try:
		threshold = float(raw_condition.get("threshold"))
	except TypeError, ValueError:
		return {
			"type": "sensor_window_threshold",
			"status": "unknown",
			"sensor": sensor_name,
			"sensor_label": SENSOR_LABELS_VI.get(sensor_name, sensor_name),
			"operator": operator,
			"reason": "missing_or_invalid_threshold",
		}

	try:
		window_seconds = int(float(raw_condition.get("window_seconds")))
	except TypeError, ValueError:
		window_seconds = 0
	if window_seconds <= 0:
		return {
			"type": "sensor_window_threshold",
			"status": "unknown",
			"sensor": sensor_name,
			"sensor_label": SENSOR_LABELS_VI.get(sensor_name, sensor_name),
			"operator": operator,
			"threshold": threshold,
			"reason": "missing_or_invalid_window_seconds",
		}

	condition = {
		"type": "sensor_window_threshold",
		"status": "unknown",
		"sensor": sensor_name,
		"sensor_label": SENSOR_LABELS_VI.get(sensor_name, sensor_name),
		"unit": SENSOR_UNITS.get(sensor_name, ""),
		"operator": operator,
		"threshold": threshold,
		"window_seconds": window_seconds,
		"aggregation": raw_condition.get("aggregation") or "any",
		"source": "telemetry_window",
	}
	if telemetry_store is None:
		condition["reason"] = "telemetry_store_not_configured"
		return condition

	limit = max(20, min(300, window_seconds * 4))
	window = telemetry_store.recent_summary_seconds(
		user_id=user_id,
		window_seconds=window_seconds,
		limit=limit,
	)
	condition["window"] = {
		"available": window.get("available"),
		"reason": window.get("reason"),
		"point_count": window.get("point_count", 0),
		"first_recorded_at": window.get("first_recorded_at"),
		"last_recorded_at": window.get("last_recorded_at"),
	}
	if not window.get("available") or window.get("reason") != "ok":
		condition["reason"] = str(window.get("reason") or "telemetry_unavailable")
		return condition

	summary_field = TELEMETRY_SUMMARY_FIELDS[sensor_name]
	summary = window.get(summary_field, {})
	if not isinstance(summary, dict) or not summary.get("available"):
		condition["reason"] = "missing_sensor_series"
		return condition

	observed_key = "max" if operator in {">", ">="} else "min"
	observed_value = summary.get(observed_key)
	condition["observed_key"] = observed_key
	condition["observed_value"] = observed_value
	condition["current_value"] = summary.get("current")
	condition["min_value"] = summary.get("min")
	condition["max_value"] = summary.get("max")
	if not isinstance(observed_value, (int, float)):
		condition["reason"] = "missing_observed_value"
		return condition

	met = compare_numeric(float(observed_value), operator, threshold)
	condition["met"] = met
	condition["status"] = "met" if met else "not_met"
	return condition


def detect_condition_sensor(normalized: str) -> str | None:
	for sensor_name, aliases in SENSOR_CONDITION_ALIASES.items():
		if any(alias in normalized for alias in aliases):
			return sensor_name
	return None


def detect_condition_window_seconds(normalized: str) -> int | None:
	patterns = (
		r"(?:trong|tong|vòng|vong|within|last)\s+(\d+(?:[.,]\d+)?)\s*(giây|giay|s|sec|secs|second|seconds|phút|phut|m|min|mins|minute|minutes)",
		r"(\d+(?:[.,]\d+)?)\s*(giây|giay|s|sec|secs|second|seconds|phút|phut|m|min|mins|minute|minutes)\s+(?:vừa rồi|vua roi|qua|gần đây|gan day|last|ago)",
	)
	for pattern in patterns:
		match = re.search(pattern, normalized)
		if not match:
			continue
		value = float(match.group(1).replace(",", "."))
		unit = match.group(2)
		if unit in {"phút", "phut", "m", "min", "mins", "minute", "minutes"}:
			value *= 60
		return max(1, int(value))
	return None


def detect_condition_operator_threshold(
	normalized: str,
	sensor_name: str,
) -> tuple[str | None, float | None]:
	operator_patterns: tuple[tuple[str, tuple[str, ...]], ...] = (
		(
			">=",
			(
				r">=\s*",
				r"ít nhất\s+",
				r"it nhat\s+",
				r"từ\s+",
				r"tu\s+",
				r"lên\s+",
				r"len\s+",
				r"đạt\s+",
				r"dat\s+",
				r"chạm\s+",
				r"cham\s+",
				r"tới\s+",
			),
		),
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
	raw_commands = parsed.get("commands")
	if isinstance(raw_commands, list):
		commands = [
			normalise_command(item, recent_actions)
			for item in raw_commands
			if isinstance(item, dict)
		]
		if commands:
			command["commands"] = commands
	return command


def command_without_group(command: dict[str, Any]) -> dict[str, Any]:
	return {key: value for key, value in command.items() if key != "commands"}


def command_list_from(command: dict[str, Any]) -> list[dict[str, Any]]:
	raw_commands = command.get("commands")
	if isinstance(raw_commands, list):
		commands = [
			command_without_group(item)
			for item in raw_commands
			if isinstance(item, dict)
		]
		return commands or [command_without_group(command)]
	return [command_without_group(command)]


def combine_commands(commands: list[dict[str, Any]]) -> dict[str, Any]:
	clean_commands = [command_without_group(command) for command in commands]
	if not clean_commands:
		return normalise_command({})
	primary = dict(clean_commands[0])
	if len(clean_commands) > 1:
		primary["commands"] = clean_commands
	return primary


def deduplicate_commands(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
	seen: set[tuple[Any, Any, Any, Any]] = set()
	deduped: list[dict[str, Any]] = []
	for command in commands:
		condition = command.get("condition")
		condition_key = None
		if isinstance(condition, dict):
			condition_key = (
				condition.get("type"),
				condition.get("sensor"),
				condition.get("operator"),
				condition.get("threshold"),
				condition.get("window_seconds"),
			)
		key = (
			command.get("action"),
			command.get("target"),
			command.get("reference"),
			condition_key,
		)
		if key in seen:
			continue
		seen.add(key)
		deduped.append(command)
	return deduped


def parse_additional_action_segments(
	text: str,
	*,
	recent_actions: list,
	focus_target: str | None,
) -> list[dict[str, Any]]:
	segments = [
		segment.strip(" ,.;")
		for segment in re.split(
			r"\b(?:với|và|va|đồng thời|dong thoi|tiện thể|tien the|and|plus)\b",
			text,
			flags=re.IGNORECASE,
		)
	]
	if len(segments) <= 1:
		return []

	commands: list[dict[str, Any]] = []
	for segment in segments[1:]:
		if not segment:
			continue
		parsed = fast_parse_local_command(segment)
		if parsed is None:
			parsed = fast_parse_contextual_command(segment, focus_target)
		if parsed is None:
			continue
		command = normalise_command(parsed, recent_actions)
		command = apply_discourse_and_explicit_target(
			command,
			segment,
			focus_target,
		)
		commands.append(command)
	return commands


def expand_multi_action_command(
	command: dict[str, Any],
	text: str,
	*,
	recent_actions: list,
	focus_target: str | None,
) -> dict[str, Any]:
	commands = command_list_from(command)
	commands.extend(
		parse_additional_action_segments(
			text,
			recent_actions=recent_actions,
			focus_target=focus_target,
		)
	)
	commands = deduplicate_commands(commands)
	return combine_commands(commands)


def apply_discourse_and_explicit_target(
	command: dict[str, Any],
	text: str,
	focus_target: str | None,
) -> dict[str, Any]:
	if command.get("action") not in {"turn_on", "turn_off", "status"}:
		return command
	explicit_target = explicit_target_from_text(text)
	if explicit_target in DEVICE_TARGETS:
		return {
			**command,
			"target": explicit_target,
			"requested_target": explicit_target,
			"reference": "none",
			"confidence": max(float(command.get("confidence") or 0.0), 0.9),
		}
	if command.get("target") is None and focus_target in DEVICE_TARGETS:
		return {
			**command,
			"target": focus_target,
			"requested_target": focus_target,
			"reference": "discourse_focus",
			"confidence": max(float(command.get("confidence") or 0.0), 0.82),
		}
	return command


def capability_from_action(action: str) -> str | None:
	return {
		"turn_on": "turn_on_device",
		"turn_off": "turn_off_device",
		"status": "get_device_status",
	}.get(action)


def build_tool_call(command: dict[str, Any]) -> dict[str, Any] | None:
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

	if not isinstance(confidence, int | float):
		confidence = 0.0 if target is None else 0.6

	confidence = max(0.0, min(float(confidence), 1.0))
	if capability_name == "get_device_status":
		return get_device_status_call(
			str(target),
			confidence=confidence,
			source="device_planner",
		)
	return set_device_state_call(
		str(target),
		capability_name == "turn_on_device",
		confidence=confidence,
		source="device_planner",
	)


def build_tool_calls(command: dict[str, Any]) -> list[dict[str, Any]]:
	return [
		tool_call
		for item in command_list_from(command)
		if (tool_call := build_tool_call(item)) is not None
	]


def tool_call_to_proposal(tool_call: dict[str, Any]) -> ToolProposal | None:
	name = tool_call.get("name")
	args = tool_call.get("args", {})
	if name == "set_device_state":
		state = args.get("state") if isinstance(args, dict) else None
		if state is True:
			name = "turn_on_device"
		elif state is False:
			name = "turn_off_device"
		else:
			return None
	if name not in {"turn_on_device", "turn_off_device", "get_device_status"}:
		return None
	if not isinstance(args, dict):
		args = {}
	confidence = tool_call.get("confidence")
	if not isinstance(confidence, int | float):
		confidence = 0.6

	return ToolProposal(
		capability_name=name,
		arguments=args,
		rationale=(
			"Planned as a native device tool call. "
			"Execution must go through the graph runtime tool node."
		),
		expected_outcome=(
			"Device state changes if requested state differs from current state."
			if name != "get_device_status"
			else "Current device state is reported without changing hardware."
		),
		confidence=max(0.0, min(float(confidence), 1.0)),
		ambiguity_detected=False,
		clarification_question=None,
	)


def build_tool_proposal(command: dict[str, Any]) -> ToolProposal | None:
	tool_call = build_tool_call(command)
	return tool_call_to_proposal(tool_call) if tool_call else None


def build_required_read_tool_calls(command: dict[str, Any]) -> list[dict[str, Any]]:
	required_calls: list[dict[str, Any]] = []
	seen: set[tuple[Any, Any]] = set()
	if "commands" in command:
		for item in command_list_from(command):
			for call in build_required_read_tool_calls(item):
				args = call.get("args", {}) if isinstance(call, dict) else {}
				key = (
					call.get("name") if isinstance(call, dict) else None,
					json.dumps(args, sort_keys=True) if isinstance(args, dict) else "",
				)
				if key in seen:
					continue
				seen.add(key)
				required_calls.append(call)
		return required_calls

	condition = command.get("condition")
	if not isinstance(condition, dict):
		return []
	sensor = condition.get("sensor")
	if not isinstance(sensor, str):
		return []
	if condition.get("type") == "sensor_window_threshold":
		window_seconds = condition.get("window_seconds")
		if isinstance(window_seconds, int | float) and int(window_seconds) > 0:
			return [
				get_telemetry_window_call(
					sensor,
					int(window_seconds),
					source="device_condition_planner",
				)
			]
	return [get_current_telemetry_call(source="device_condition_planner")]


class DeviceControlAgent:
	def __init__(
		self,
		llm: LLMService,
		tool_runner: ToolRunner,
		telemetry_store: Any | None = None,
	) -> None:
		self.llm = llm
		self.tool_runner = tool_runner
		self.telemetry_store = telemetry_store
		self.condition_evaluator = DeviceConditionEvaluator(telemetry_store)

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
		focus_target = context.get("conversation_focus_target")
		fast_parsed = (
			fast_parse_local_command(message.text)
			if should_use_local_fast_path(message.text)
			else None
		)
		if fast_parsed is None:
			fast_parsed = fast_parse_contextual_command(message.text, focus_target)
		if fast_parsed is not None:
			command = normalise_command(
				fast_parsed,
				device_memory_context.get("recent_actions", []),
			)
			command = apply_discourse_and_explicit_target(
				command,
				message.text,
				str(focus_target) if isinstance(focus_target, str) else None,
			)
			return expand_multi_action_command(
				command,
				message.text,
				recent_actions=device_memory_context.get("recent_actions", []),
				focus_target=str(focus_target)
				if isinstance(focus_target, str)
				else None,
			)
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
					+ "\n\nCurrent discourse focus target:\n"
					+ str(focus_target or "none")
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
		command = apply_discourse_and_explicit_target(
			command,
			message.text,
			str(focus_target) if isinstance(focus_target, str) else None,
		)
		return expand_multi_action_command(
			command,
			message.text,
			recent_actions=device_memory_context.get("recent_actions", []),
			focus_target=str(focus_target) if isinstance(focus_target, str) else None,
		)

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
		tool_calls = build_tool_calls(command)
		log_agent(
			f"DeviceControl: {command['action']} -> {command['target']}",
			data={
				"confidence": command.get("confidence"),
				"reference": command.get("reference"),
				"has_tool_call": bool(tool_calls),
				"command_count": len(command_list_from(command)),
			},
			detail=(f"tool_calls={len(tool_calls)}" if tool_calls else "no tool_call"),
		)

		return self.build_plan_response(command, tool_calls)

	def ground_tool_plan(
		self,
		response: AgentResponse,
		*,
		user_text: str,
		sensor_snapshot: dict | None,
		user_id: str | None,
	) -> AgentResponse:
		raw_report = response.metadata.get("specialist_report")
		if not isinstance(raw_report, dict):
			return response
		analysis = raw_report.get("analysis_payload", {})
		if not isinstance(analysis, dict):
			return response
		command = analysis.get("parsed_command")
		if not isinstance(command, dict):
			return response
		grounded_commands = [
			self.condition_evaluator.evaluate(
				item,
				user_text=user_text,
				sensor_snapshot=sensor_snapshot,
				user_id=user_id,
			)
			for item in command_list_from(command)
		]
		command = combine_commands(grounded_commands)
		tool_calls = build_tool_calls(command)
		grounded_response = self.build_plan_response(command, tool_calls)
		grounded_response.metadata["planning_stage"] = "grounded"
		return grounded_response

	def build_plan_response(
		self,
		command: dict[str, Any],
		tool_calls: list[dict[str, Any]] | dict[str, Any] | None,
	) -> AgentResponse:
		if isinstance(tool_calls, dict):
			tool_calls = [tool_calls]
		elif tool_calls is None:
			tool_calls = []
		tool_proposals = [
			proposal
			for tool_call in tool_calls
			if (proposal := tool_call_to_proposal(tool_call)) is not None
		]
		commands = command_list_from(command)
		clarification_question = None
		needs_clarification = any(
			item.get("action") in {"turn_on", "turn_off", "status"}
			and item.get("target") is None
			for item in commands
		)
		summary = "unknown_or_ambiguous_command"
		conditions = [
			item.get("condition")
			for item in commands
			if isinstance(item.get("condition"), dict)
		]
		if needs_clarification and tool_calls:
			summary = "partial_tool_call_ready_awaiting_target_clarification"
			clarification_question = "Bạn muốn mình điều khiển thiết bị nào?"
		elif needs_clarification:
			summary = "awaiting_target_clarification"
			clarification_question = "Bạn muốn mình điều khiển thiết bị nào?"
		elif any(
			isinstance(condition, dict) and condition.get("status") == "not_met"
			for condition in conditions
		):
			summary = "condition_not_met"
		elif any(
			isinstance(condition, dict) and condition.get("status") == "unknown"
			for condition in conditions
		):
			summary = "condition_unknown"
		elif (
			any(
				isinstance(condition, dict) and condition.get("status") == "met"
				for condition in conditions
			)
			and tool_calls
		):
			summary = "condition_met_tool_call_ready"
		elif tool_calls:
			summary = "tool_call_ready"

		required_tool_calls = build_required_read_tool_calls(command)
		report = {
			"parsed_command": command,
			"parsed_commands": commands,
			"tool_calls": tool_calls,
			"required_tool_calls": required_tool_calls,
			"tool_proposals": (
				[proposal.model_dump(mode="json") for proposal in tool_proposals]
			),
			"device_status": self.tool_runner.get_device_status_report(),
		}
		analysis_payload = dict(report)
		specialist_report = SpecialistReport(
			specialist_name=self.name,
			summary=summary,
			tool_proposals=tool_proposals,
			clarification_question=clarification_question,
			analysis_payload=analysis_payload,
		)
		report["specialist_report"] = specialist_report.model_dump(mode="json")

		return AgentResponse(
			text=json.dumps(report, ensure_ascii=False),
			agent_name=self.name,
			tools_used=[],
			metadata={**report, "planning_stage": "planned"},
		)
