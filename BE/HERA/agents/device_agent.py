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
from domain.devices import DEVICE_TARGETS, DEVICE_VALUE_SPECS, SENSOR_VALUE_SPECS
from domain.devices.device_catalog import SCENE_CATALOG, SCENE_LABELS
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
	set_device_value_call,
	set_sensor_value_call,
)
from schemas import SpecialistReport, ToolProposal
from telemetry import sensor_value

DEVICE_LABEL_TARGETS = {
	"Main LED": "main_led",
	"NeoPixel LED": "neo_led",
	"WS2812 LED": "ws2812",
	"Relay": "relay",
	"Mini fan": "mini_fan",
}

# Sensor metadata used by condition evaluator (runtime correctness, not NLU)
SENSOR_CONDITION_ALIASES = {
	"temperature": ("temperature", "temp"),
	"humidity": ("humidity",),
	"light": ("light",),
	"anomaly": ("anomaly",),
}

SENSOR_LABELS_VI = {
	"temperature": "nhiá»‡t Ä‘á»™",
	"humidity": "Ä‘á»™ áº©m",
	"light": "Ã¡nh sÃ¡ng",
	"anomaly": "Ä‘iá»ƒm báº¥t thÆ°á»ng",
}

SENSOR_UNITS = {
	"temperature": "Â°C",
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


def explicit_target_from_text(text: str) -> str | None:
	"""Extract an explicit device target from text using canonical device IDs.

	This is used for discourse focus extraction (grounding), not for intent
	routing. It only matches when a canonical device ID appears literally
	in the user text.
	"""
	normalized = normalize_text(text)
	if not normalized:
		return None
	# Check canonical device IDs directly â€” no keyword token sets needed
	canonical_ids = {
		"main_led": ("main led", "main_led"),
		"neo_led": ("neo led", "neo_led", "neopixel"),
		"ws2812": ("ws2812",),
		"relay": ("relay",),
		"mini_fan": ("mini fan", "mini_fan"),
	}
	for target, patterns in canonical_ids.items():
		if any(pattern in normalized for pattern in patterns):
			return target
	# Check group targets
	group_markers = {
		"all_devices": ("all devices", "all_devices"),
		"all_lights": ("all lights", "all_lights"),
	}
	for target, patterns in group_markers.items():
		if any(pattern in normalized for pattern in patterns):
			return target
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
	except (TypeError, ValueError):
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
	current_value = sensor_value(sensors, sensor_name)
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
	except (TypeError, ValueError):
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
	except (TypeError, ValueError):
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
		r"(?:trong|tong|vÃ²ng|vong|within|last)\s+(\d+(?:[.,]\d+)?)\s*(giÃ¢y|giay|s|sec|secs|second|seconds|phÃºt|phut|m|min|mins|minute|minutes)",
		r"(\d+(?:[.,]\d+)?)\s*(giÃ¢y|giay|s|sec|secs|second|seconds|phÃºt|phut|m|min|mins|minute|minutes)\s+(?:vá»«a rá»“i|vua roi|qua|gáº§n Ä‘Ã¢y|gan day|last|ago)",
	)
	for pattern in patterns:
		match = re.search(pattern, normalized)
		if not match:
			continue
		value = float(match.group(1).replace(",", "."))
		unit = match.group(2)
		if unit in {"phÃºt", "phut", "m", "min", "mins", "minute", "minutes"}:
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
				r"Ã­t nháº¥t\s+",
				r"it nhat\s+",
				r"tá»«\s+",
				r"tu\s+",
				r"lÃªn\s+",
				r"len\s+",
				r"Ä‘áº¡t\s+",
				r"dat\s+",
				r"cháº¡m\s+",
				r"cham\s+",
				r"tá»›i\s+",
			),
		),
		("<=", (r"<=\s*", r"tá»‘i Ä‘a\s+", r"toi da\s+")),
		(
			">",
			(
				r">\s*",
				r"trÃªn\s+",
				r"tren\s+",
				r"cao hÆ¡n\s+",
				r"cao hon\s+",
				r"lá»›n hÆ¡n\s+",
				r"lon hon\s+",
				r"hÆ¡n\s+",
				r"hon\s+",
			),
		),
		(
			"<",
			(
				r"<\s*",
				r"dÆ°á»›i\s+",
				r"duoi\s+",
				r"tháº¥p hÆ¡n\s+",
				r"thap hon\s+",
				r"nhá» hÆ¡n\s+",
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
		if any(marker in normalized for marker in ("cao", "nÃ³ng", "nong", "high")):
			return ">", float(NORMAL_TEMP_MAX)
		if any(
			marker in normalized for marker in ("tháº¥p", "thap", "láº¡nh", "lanh", "low")
		):
			return "<", float(NORMAL_TEMP_MIN)
	if sensor_name == "humidity":
		if any(marker in normalized for marker in ("cao", "áº©m", "am", "high")):
			return ">", float(NORMAL_HUMI_MAX)
		if any(
			marker in normalized for marker in ("tháº¥p", "thap", "khÃ´", "kho", "low")
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
	if action not in {
		"turn_on",
		"turn_off",
		"status",
		"set_device_value",
		"set_sensor_value",
		"unknown",
	}:
		action = "unknown"
	if reference not in {"none", "recent_changed_devices"}:
		reference = "none"
	if reference == "recent_changed_devices":
		target = target_from_recent_changed_devices(recent_actions or [])
	if action == "set_device_value":
		if target not in DEVICE_VALUE_SPECS:
			target = None
		prop = parsed.get("property")
		if not isinstance(prop, str) or prop not in DEVICE_VALUE_SPECS.get(
			str(target),
			{},
		):
			prop = None
	else:
		prop = None
	if action != "set_sensor_value" and target not in DEVICE_TARGETS:
		target = None
	sensor = parsed.get("sensor")
	if action == "set_sensor_value":
		if sensor not in SENSOR_VALUE_SPECS:
			sensor = None
		target = None
	else:
		sensor = None
	if action == "unknown":
		target = None
		sensor = None
	if requested_action not in {
		"turn_on",
		"turn_off",
		"status",
		"set_device_value",
		"set_sensor_value",
	}:
		requested_action = (
			action
			if action
			in {"turn_on", "turn_off", "status", "set_device_value", "set_sensor_value"}
			else None
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
	if action == "set_device_value":
		command["property"] = prop
		command["value"] = parsed.get("value")
	if action == "set_sensor_value":
		command["sensor"] = sensor
		command["value"] = parsed.get("value")
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
			command.get("sensor"),
			command.get("property"),
			command.get("value"),
			command.get("reference"),
			condition_key,
		)
		if key in seen:
			continue
		seen.add(key)
		deduped.append(command)
	return deduped


def expand_multi_action_command(
	command: dict[str, Any],
	text: str,
	*,
	recent_actions: list,
	focus_target: str | None,
) -> dict[str, Any]:
	_ = text, recent_actions, focus_target
	commands = command_list_from(command)
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
		"set_device_value": "set_device_value",
		"set_sensor_value": "set_sensor_value",
	}.get(action)


def build_tool_call(command: dict[str, Any]) -> dict[str, Any] | None:
	condition = command.get("condition")
	if isinstance(condition, dict) and condition.get("status") != "met":
		return None

	capability_name = capability_from_action(command["action"])
	if capability_name is None:
		return None

	if capability_name == "set_sensor_value":
		sensor = command.get("sensor")
		if sensor not in SENSOR_VALUE_SPECS or "value" not in command:
			return None
		confidence = command.get("confidence")
		if not isinstance(confidence, int | float):
			confidence = 0.6
		return set_sensor_value_call(
			str(sensor),
			command.get("value"),
			confidence=max(0.0, min(float(confidence), 1.0)),
			source="device_planner",
		)

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
	if capability_name == "set_device_value":
		prop = command.get("property")
		if (
			target not in DEVICE_VALUE_SPECS
			or not isinstance(prop, str)
			or prop not in DEVICE_VALUE_SPECS.get(str(target), {})
			or "value" not in command
		):
			return None
		return set_device_value_call(
			str(target),
			prop,
			command.get("value"),
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
	"""Expand a parsed command (including activate_scene) into tool calls."""
	# Scene expansion: convert activate_scene → sequence of state/value calls
	if command.get("action") == "activate_scene":
		scene_id = command.get("scene")
		if scene_id not in SCENE_CATALOG:
			return []
		result: list[dict[str, Any]] = []
		for step in SCENE_CATALOG[scene_id]:
			if step["type"] == "state":
				result.append(
					set_device_state_call(
						step["target"],
						step["state"],
						confidence=1.0,
						source="scene_planner",
					)
				)
			elif step["type"] == "value":
				result.append(
					set_device_value_call(
						step["target"],
						step["property"],
						step["value"],
						confidence=1.0,
						source="scene_planner",
					)
				)
		return result
	# Normal single/multi-action expansion
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
	if name not in {
		"turn_on_device",
		"turn_off_device",
		"get_device_status",
		"set_device_value",
		"set_sensor_value",
	}:
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
			"Requested value changes if it differs from current telemetry."
			if name in {"set_device_value", "set_sensor_value"}
			else
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
			(
				item.get("action") in {"turn_on", "turn_off", "status"}
				and item.get("target") is None
			)
			or (
				item.get("action") == "set_device_value"
				and (
					item.get("target") is None
					or item.get("property") is None
					or "value" not in item
				)
			)
			or (
				item.get("action") == "set_sensor_value"
				and (item.get("sensor") is None or "value" not in item)
			)
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
			clarification_question = "Báº¡n muá»‘n mÃ¬nh Ä‘iá»u khiá»ƒn thiáº¿t bá»‹ nÃ o?"
		elif needs_clarification:
			summary = "awaiting_target_clarification"
			clarification_question = "Báº¡n muá»‘n mÃ¬nh Ä‘iá»u khiá»ƒn thiáº¿t bá»‹ nÃ o?"
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
