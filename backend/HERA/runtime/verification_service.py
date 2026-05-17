"""Verification checks after tool execution."""

from __future__ import annotations

from typing import Any

from domain.devices import DEVICE_STATUS_KEYS
from domain.devices.device_catalog import normalize_color_value
from schemas import (
	PolicyDecision,
	ToolExecutionResult,
	ToolProposal,
	VerificationResult,
)

DEVICE_NAME_BY_STATUS_KEY = {
	status_key: device_name for device_name, status_key in DEVICE_STATUS_KEYS.items()
}


class VerificationService:
	"""Verifies execution outcomes against cached device state."""

	def verify(
		self,
		proposal: ToolProposal,
		execution_result: ToolExecutionResult,
		policy_decision: PolicyDecision,
	) -> VerificationResult:
		if policy_decision.decision in {"ask", "deny"}:
			return VerificationResult(
				status="rejected",
				source="policy",
				confidence=1.0,
				details={
					"policy_decision": policy_decision.model_dump(mode="json"),
				},
			)

		if policy_decision.decision == "noop":
			return VerificationResult(
				status="noop",
				source="cached_state",
				confidence=1.0,
				details={
					"reason": policy_decision.reason,
				},
			)

		if execution_result.status == "status_requested":
			return VerificationResult(
				status="verified",
				source="cached_state",
				confidence=1.0,
				details={"reason": "read_only_status_request"},
			)

		if not execution_result.ok:
			return VerificationResult(
				status="failed",
				source="none",
				confidence=0.8,
				details={"reason": execution_result.reason},
			)

		commands_sent = execution_result.raw_metadata.get("commands_sent", [])
		if not commands_sent:
			return VerificationResult(
				status="noop",
				source="cached_state",
				confidence=1.0,
				details={"reason": execution_result.reason},
			)

		after_state = execution_result.after_state
		if not after_state:
			return VerificationResult(
				status="unverified",
				source="none",
				confidence=0.0,
				details={"reason": "missing_after_state"},
			)

		mismatches: list[dict] = []
		for command in commands_sent:
			entity_type = command.get("entity_type")
			if entity_type == "device_value":
				devices = after_state.get("devices", {})
				device = {}
				if isinstance(devices, dict):
					device = devices.get(command.get("target")) or devices.get(
						command.get("device_key")
					)
				observed = (
					device.get(command.get("field")) if isinstance(device, dict) else None
				)
				expected = command.get("expected_value")
				if not self._same_value(observed, expected):
					mismatches.append(
						{
							"device": command.get("target"),
							"property": command.get("property"),
							"expected": expected,
							"observed": observed,
						}
					)
				continue

			if entity_type == "sensor_value":
				sensors = after_state.get("sensors", {})
				observed = (
					self._sensor_value_from_snapshot(
						sensors,
						str(command.get("sensor") or ""),
					)
					if isinstance(sensors, dict)
					else None
				)
				expected = command.get("expected_value")
				if not self._same_value(observed, expected):
					mismatches.append(
						{
							"sensor": command.get("sensor"),
							"expected": expected,
							"observed": observed,
						}
					)
				continue

			device_key = command.get("device_key")
			device_name = DEVICE_NAME_BY_STATUS_KEY.get(device_key)
			if device_name is None:
				mismatches.append(
					{
						"device_key": device_key,
						"reason": "unknown_device_key",
					}
				)
				continue

			expected = command.get("expected_state", command.get("params"))
			observed = after_state.get(device_name)
			if observed is not expected:
				mismatches.append(
					{
						"device": device_name,
						"expected": expected,
						"observed": observed,
					}
				)

		if mismatches:
			if execution_result.raw_metadata.get("double_check_timed_out"):
				return VerificationResult(
					status="timeout",
					source="state_readback",
					confidence=0.3,
					details={
						"reason": "state_readback_timeout",
						"mismatches": mismatches,
					},
				)
			return VerificationResult(
				status="failed",
				source="state_readback",
				confidence=0.9,
				details={"mismatches": mismatches},
			)

		return VerificationResult(
			status="verified",
			source="state_readback",
			confidence=0.9,
			details={
				"commands_checked": len(commands_sent),
				"capability_name": proposal.capability_name,
			},
		)

	@staticmethod
	def _sensor_value_from_snapshot(sensors: dict, sensor: str) -> Any:
		if sensor in {"temperature", "humidity"}:
			dht20 = sensors.get("dht20")
			if isinstance(dht20, dict) and sensor in dht20:
				return dht20.get(sensor)
			return sensors.get(sensor)
		if sensor == "light":
			light = sensors.get("light")
			return light.get("value") if isinstance(light, dict) else light
		if sensor == "gas":
			gas = sensors.get("gas")
			return gas.get("value") if isinstance(gas, dict) else gas
		if sensor == "gas_detected":
			gas = sensors.get("gas")
			if isinstance(gas, dict) and "detected" in gas:
				return gas.get("detected")
			return sensors.get("gas_detected")
		return sensors.get(sensor)

	@staticmethod
	def _same_value(left: Any, right: Any) -> bool:
		left_color = normalize_color_value(left)
		right_color = normalize_color_value(right)
		if left_color is not None or right_color is not None:
			return left_color == right_color
		return left == right
