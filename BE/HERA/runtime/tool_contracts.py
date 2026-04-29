"""Schema-level tool call contracts used by graph planner/runtime nodes."""

from __future__ import annotations

from typing import Any

DEVICE_TOOL_NAMES = {
	"get_device_status",
	"set_device_state",
	"set_device_value",
	"set_sensor_value",
}

TELEMETRY_TOOL_NAMES = {
	"get_current_telemetry",
	"get_telemetry_window",
}

WEB_TOOL_NAMES = {
	"search_web",
	"fetch_web_page",
}

MEMORY_TOOL_NAMES = {
	"retrieve_memory",
	"store_memory",
}

SUPPORTED_TOOL_NAMES = (
	DEVICE_TOOL_NAMES | TELEMETRY_TOOL_NAMES | WEB_TOOL_NAMES | MEMORY_TOOL_NAMES
)


def make_tool_call(
	name: str,
	args: dict[str, Any] | None = None,
	*,
	confidence: float = 0.6,
	source: str = "planner",
) -> dict[str, Any]:
	"""Build the normalized tool-call shape passed between graph nodes."""
	return {
		"name": name,
		"args": args or {},
		"confidence": max(0.0, min(float(confidence), 1.0)),
		"source": source,
	}


def get_device_status_call(
	device_target: str,
	*,
	confidence: float = 0.6,
	source: str = "planner",
) -> dict[str, Any]:
	return make_tool_call(
		"get_device_status",
		{"device_target": device_target},
		confidence=confidence,
		source=source,
	)


def set_device_state_call(
	device_target: str,
	state: bool,
	*,
	confidence: float = 0.6,
	source: str = "planner",
) -> dict[str, Any]:
	return make_tool_call(
		"set_device_state",
		{"device_target": device_target, "state": bool(state)},
		confidence=confidence,
		source=source,
	)


def set_device_value_call(
	device_target: str,
	property_name: str,
	value: Any,
	*,
	confidence: float = 0.6,
	source: str = "planner",
) -> dict[str, Any]:
	return make_tool_call(
		"set_device_value",
		{
			"device_target": device_target,
			"property": property_name,
			"value": value,
		},
		confidence=confidence,
		source=source,
	)


def set_sensor_value_call(
	sensor: str,
	value: Any,
	*,
	confidence: float = 0.6,
	source: str = "planner",
) -> dict[str, Any]:
	return make_tool_call(
		"set_sensor_value",
		{"sensor": sensor, "value": value},
		confidence=confidence,
		source=source,
	)


def get_current_telemetry_call(
	*,
	confidence: float = 1.0,
	source: str = "planner",
) -> dict[str, Any]:
	return make_tool_call(
		"get_current_telemetry",
		{},
		confidence=confidence,
		source=source,
	)


def get_telemetry_window_call(
	sensor: str,
	window_seconds: int,
	*,
	confidence: float = 1.0,
	source: str = "planner",
) -> dict[str, Any]:
	return make_tool_call(
		"get_telemetry_window",
		{"sensor": sensor, "window_seconds": window_seconds},
		confidence=confidence,
		source=source,
	)
