"""Deterministic policy checks before tool execution."""

from __future__ import annotations

from typing import Any

from domain.devices import (
	DEVICE_TARGETS,
	coerce_device_value,
	coerce_sensor_value,
	normalize_device_target,
)
from domain.devices.device_catalog import normalize_color_value
from schemas import CapabilitySpec, PolicyDecision, ToolProposal
from telemetry.schema import device_status


class PolicyEngine:
	"""Applies early safety rules before physical side effects."""

	def evaluate(
		self,
		proposal: ToolProposal,
		capability: CapabilitySpec,
		runtime_state: dict[str, Any],
	) -> PolicyDecision:
		if proposal.ambiguity_detected:
			return PolicyDecision(
				decision="ask",
				reason="ambiguous_proposal",
				user_visible_message=(
					proposal.clarification_question
					or "I need a clearer device target before controlling anything."
				),
			)

		if capability.effect_type == "read":
			return PolicyDecision(
				decision="allow",
				reason="read_only_capability",
			)

		network = runtime_state.get("network", {})
		if network and network.get("mqtt_connected") is False:
			return PolicyDecision(
				decision="deny",
				reason="device_reports_mqtt_offline",
				user_visible_message=(
					"The device appears offline, so I will not send this command."
				),
			)

		if proposal.capability_name == "set_sensor_value":
			return self._evaluate_sensor_value(proposal, runtime_state)

		if proposal.capability_name == "set_device_value":
			return self._evaluate_device_value(proposal, runtime_state)

		target = self._normalized_target(proposal)
		if target is None:
			return PolicyDecision(
				decision="ask",
				reason="missing_or_invalid_target",
				user_visible_message=("Which device should I control?"),
			)

		if target == "all_devices" and not proposal.arguments.get("_confirmed"):
			return PolicyDecision(
				decision="ask",
				reason="broad_all_devices_scope_requires_confirmation",
				user_visible_message=(
					"Please confirm before controlling every supported device at once."
				),
			)

		requested_state = self._requested_state(proposal)
		if requested_state is not None and self._already_in_requested_state(
			target,
			requested_state,
			runtime_state,
		):
			return PolicyDecision(
				decision="noop",
				reason="already_in_requested_state",
				user_visible_message="The requested device state is already set.",
			)

		return PolicyDecision(
			decision="allow",
			reason="policy_allowed",
		)

	def _evaluate_device_value(
		self,
		proposal: ToolProposal,
		runtime_state: dict[str, Any],
	) -> PolicyDecision:
		coerced = coerce_device_value(
			proposal.arguments.get("device_target"),
			proposal.arguments.get("property"),
			proposal.arguments.get("value"),
		)
		if not coerced.get("ok"):
			return PolicyDecision(
				decision="ask",
				reason=str(coerced.get("reason") or "invalid_device_value"),
				user_visible_message=(
					"Which supported device value should I set?"
				),
			)
		if self._already_in_requested_device_value(coerced, runtime_state):
			return PolicyDecision(
				decision="noop",
				reason="already_in_requested_value",
				user_visible_message="The requested device value is already set.",
			)
		return PolicyDecision(decision="allow", reason="policy_allowed")

	def _evaluate_sensor_value(
		self,
		proposal: ToolProposal,
		runtime_state: dict[str, Any],
	) -> PolicyDecision:
		coerced = coerce_sensor_value(
			proposal.arguments.get("sensor"),
			proposal.arguments.get("value"),
		)
		if not coerced.get("ok"):
			return PolicyDecision(
				decision="ask",
				reason=str(coerced.get("reason") or "invalid_sensor_value"),
				user_visible_message=("Which supported sensor value should I set?"),
			)
		if self._already_in_requested_sensor_value(coerced, runtime_state):
			return PolicyDecision(
				decision="noop",
				reason="already_in_requested_value",
				user_visible_message="The requested sensor value is already set.",
			)
		return PolicyDecision(decision="allow", reason="policy_allowed")

	@staticmethod
	def _requested_state(proposal: ToolProposal) -> bool | None:
		if proposal.capability_name == "turn_on_device":
			return True
		if proposal.capability_name == "turn_off_device":
			return False
		return None

	@staticmethod
	def _normalized_target(proposal: ToolProposal) -> str | None:
		return normalize_device_target(proposal.arguments.get("device_target"))

	@staticmethod
	def _already_in_requested_state(
		target: str,
		requested_state: bool,
		runtime_state: dict[str, Any],
	) -> bool:
		if target not in DEVICE_TARGETS:
			return False

		devices = runtime_state.get("devices", {})
		if not isinstance(devices, dict):
			return False

		current_states = []
		for _, device_key, _ in DEVICE_TARGETS[target]:
			current_states.append(device_status({"devices": devices}, device_key))
		return bool(current_states) and all(
			current_state is requested_state for current_state in current_states
		)

	@staticmethod
	def _already_in_requested_device_value(
		coerced: dict,
		runtime_state: dict[str, Any],
	) -> bool:
		devices = runtime_state.get("devices", {})
		if not isinstance(devices, dict):
			return False
		device_key = coerced.get("device_key")
		field = coerced.get("field")
		current = None
		device = devices.get(device_key)
		if isinstance(device, dict):
			current = device.get(field)
		else:
			flat_fields = {
				("neo_led", "brightness"): "strip_brightness",
				("ws2812", "brightness"): "ws2812_brightness",
				("ws2812", "color"): "ws2812_color",
				("mini_fan", "speed"): "fan_speed",
			}
			current = devices.get(flat_fields.get((device_key, field), ""))
		return PolicyEngine._same_value(current, coerced.get("value"))

	@staticmethod
	def _already_in_requested_sensor_value(
		coerced: dict,
		runtime_state: dict[str, Any],
	) -> bool:
		sensors = runtime_state.get("sensors", {})
		if not isinstance(sensors, dict):
			return False
		sensor = coerced.get("sensor")
		current = None
		if sensor in {"temperature", "humidity"}:
			dht20 = sensors.get("dht20")
			current = (
				dht20.get(sensor)
				if isinstance(dht20, dict) and sensor in dht20
				else sensors.get(sensor)
			)
		elif sensor == "light":
			light = sensors.get("light")
			current = light.get("value") if isinstance(light, dict) else light
		elif sensor == "gas":
			gas = sensors.get("gas")
			current = gas.get("value") if isinstance(gas, dict) else gas
		elif sensor == "gas_detected":
			gas = sensors.get("gas")
			current = (
				gas.get("detected")
				if isinstance(gas, dict) and "detected" in gas
				else sensors.get("gas_detected")
			)
		return PolicyEngine._same_value(current, coerced.get("value"))

	@staticmethod
	def _same_value(left: Any, right: Any) -> bool:
		left_color = normalize_color_value(left)
		right_color = normalize_color_value(right)
		if left_color is not None or right_color is not None:
			return left_color == right_color
		return left == right
