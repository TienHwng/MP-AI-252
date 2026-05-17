"""Canonical runtime capability registry."""

from __future__ import annotations

from domain.devices import (
	DEVICE_TOOL_PARAMS,
	DEVICE_VALUE_TOOL_PARAMS,
	SENSOR_VALUE_TOOL_PARAMS,
)
from schemas import CapabilitySpec

EMPTY_PARAMS = {
	"type": "object",
	"properties": {},
	"required": [],
}

TELEMETRY_WINDOW_PARAMS = {
	"type": "object",
	"properties": {
		"sensor": {
			"type": "string",
			"description": "Optional sensor name to focus on.",
		},
		"window_seconds": {
			"type": "integer",
			"description": "Lookback window in seconds.",
			"minimum": 1,
		},
		"limit": {
			"type": "integer",
			"description": "Maximum telemetry points to inspect.",
			"minimum": 1,
		},
	},
	"required": ["window_seconds"],
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
						"the executor will not send a duplicate command. "
						"mini_fan starts at full PWM (1023) so the motor can spin up."
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
					name="get_current_telemetry",
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
				CapabilitySpec(
					name="get_telemetry_window",
					description=(
						"Read a recent telemetry summary window for threshold "
						"checks and anomaly diagnostics."
					),
					parameters=TELEMETRY_WINDOW_PARAMS,
					effect_type="read",
					risk_level="low",
					supports_idempotency=True,
					requires_confirmation=False,
				),
				CapabilitySpec(
					name="set_device_value",
					description=(
						"Set an adjustable device value through MQTT RPC. "
						"Supported pairs are neo_led brightness (0..255), "
						"ws2812 brightness (0..255), ws2812 color (#RRGGBB), "
						"and mini_fan speed (0..1023)."
					),
					parameters=DEVICE_VALUE_TOOL_PARAMS,
					effect_type="write",
					risk_level="medium",
					supports_idempotency=True,
					requires_confirmation=False,
					verifier_name="device_value_readback",
				),
				CapabilitySpec(
					name="set_sensor_value",
					description=(
						"Override a simulator sensor value through MQTT RPC. "
						"Use only in simulation mode for temperature, humidity, "
						"light, gas, or gas_detected."
					),
					parameters=SENSOR_VALUE_TOOL_PARAMS,
					effect_type="write",
					risk_level="medium",
					supports_idempotency=True,
					requires_confirmation=False,
					verifier_name="sensor_value_readback",
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
