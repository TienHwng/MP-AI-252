"""Canonical runtime capability registry."""

from __future__ import annotations

from domain.devices import DEVICE_TOOL_PARAMS
from schemas import CapabilitySpec

EMPTY_PARAMS = {
	"type": "object",
	"properties": {},
	"required": [],
}


class CapabilityRegistry:
	"""Defines capabilities available to the central tool runtime."""

	def __init__(self) -> None:
		self._capabilities = {
			spec.name: spec
			for spec in (
				CapabilitySpec(
					name="get_device_status",
					description=(
						"Get current states for main_led, neo_led, ws2812, "
						"relay, and mini_fan."
					),
					parameters=EMPTY_PARAMS,
					effect_type="read",
					risk_level="low",
					supports_idempotency=True,
					requires_confirmation=False,
				),
				CapabilitySpec(
					name="turn_on_device",
					description=(
						"Turn ON a device only when needed. If already ON, "
						"the executor will not send a duplicate command."
					),
					parameters=DEVICE_TOOL_PARAMS,
					effect_type="write",
					risk_level="medium",
					supports_idempotency=True,
					requires_confirmation=False,
					verifier_name="device_state_readback",
				),
				CapabilitySpec(
					name="turn_off_device",
					description=(
						"Turn OFF a device only when needed. If already OFF, "
						"the executor will not send a duplicate command."
					),
					parameters=DEVICE_TOOL_PARAMS,
					effect_type="write",
					risk_level="medium",
					supports_idempotency=True,
					requires_confirmation=False,
					verifier_name="device_state_readback",
				),
				CapabilitySpec(
					name="get_sensor_status",
					description=(
						"Get current sensor readings: temperature, humidity, "
						"light, anomaly score, device states, and network state."
					),
					parameters=EMPTY_PARAMS,
					effect_type="read",
					risk_level="low",
					supports_idempotency=True,
					requires_confirmation=False,
				),
			)
		}

	def get(self, name: str) -> CapabilitySpec | None:
		return self._capabilities.get(name)

	def require(self, name: str) -> CapabilitySpec:
		spec = self.get(name)
		if spec is None:
			raise KeyError(f"Unknown runtime capability: {name}")
		return spec

	def list_specs(self) -> list[CapabilitySpec]:
		return list(self._capabilities.values())

	def get_tool_definition(self, name: str) -> dict:
		spec = self.require(name)
		return {
			"type": "function",
			"function": {
				"name": spec.name,
				"description": spec.description,
				"parameters": spec.parameters,
			},
		}
