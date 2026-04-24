"""Deterministic policy checks before tool execution."""

from __future__ import annotations

from typing import Any

from domain.devices import (
	DEVICE_TARGETS,
	normalize_device_target,
)
from schemas import CapabilitySpec, PolicyDecision, ToolProposal


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

		current_states = [
			devices.get(device_key) for _, device_key, _ in DEVICE_TARGETS[target]
		]
		return bool(current_states) and all(
			current_state is requested_state for current_state in current_states
		)
