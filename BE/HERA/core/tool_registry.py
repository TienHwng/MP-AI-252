"""
Tool Registry
=============
Compatibility wrapper for OpenAI-style tool definitions.
Runtime-owned execution now goes through ``runtime.ToolRunner``.
"""

from __future__ import annotations

import json
from typing import Any

from domain.devices.device_executor import DeviceExecutor
from runtime.capability_registry import CapabilityRegistry

from core.mqtt_service import MQTTService


class ToolRegistry:
	"""
	Holds tool definitions (JSON schemas for the LLM) and tool executors.
	"""

	def __init__(
		self,
		mqtt: MQTTService,
		*,
		capabilities: CapabilityRegistry | None = None,
		device_executor: DeviceExecutor | None = None,
	) -> None:
		self.mqtt = mqtt
		self.capabilities = capabilities or CapabilityRegistry()
		self.device_executor = device_executor or DeviceExecutor(mqtt)
		self.executors: dict[str, Any] = {}
		self.definitions: list[dict] = []
		self.register_builtins()

	def execute(self, name: str, args: dict) -> str:
		fn = self.executors.get(name)
		if fn is None:
			return f"Unknown tool: {name}"
		return fn(args)

	def get_definitions(self, names: list[str] | None = None) -> list[dict]:
		"""Return tool schemas, optionally filtered by name list."""
		if names is None:
			return list(self.definitions)
		name_set = set(names)
		return [d for d in self.definitions if d["function"]["name"] in name_set]

	def register(self, name: str, desc: str, executor, params=None) -> None:
		self.definitions.append(
			{
				"type": "function",
				"function": {
					"name": name,
					"description": desc,
					"parameters": params
					or {
						"type": "object",
						"properties": {},
						"required": [],
					},
				},
			}
		)
		self.executors[name] = executor

	def register_capability(self, name: str, executor) -> None:
		spec = self.capabilities.require(name)
		self.definitions.append(self.capabilities.get_tool_definition(name))
		self.executors[spec.name] = executor

	def get_device_status_report(self) -> dict:
		return self.device_executor.get_device_status_report()

	def control_device_state(self, raw_target: Any, state: bool) -> dict:
		return self.device_executor.control_device_state(raw_target, state)

	@staticmethod
	def format_device_control_result(result: dict) -> str:
		if not result.get("ok"):
			valid = ", ".join(result.get("valid_targets", []))
			return f"Invalid device_target. Use one of: {valid}."

		action = "ON" if result["requested_state"] else "OFF"
		changed = result.get("changed", [])
		unchanged = result.get("unchanged", [])
		if changed and unchanged:
			return (
				f"Turned {', '.join(changed)} {action}. "
				f"Already {action}: {', '.join(unchanged)}."
			)
		if changed:
			return f"Turned {', '.join(changed)} {action}."
		return f"Already {action}: {', '.join(unchanged)}. No command sent."

	def register_builtins(self) -> None:
		mqtt = self.mqtt

		def device_status_report() -> str:
			return json.dumps(self.get_device_status_report(), indent=2)

		def set_device_state(args: dict, state: bool) -> str:
			result = self.control_device_state(args.get("device_target"), state)
			return self.format_device_control_result(result)

		self.register_capability(
			"get_device_status",
			lambda args: device_status_report(),
		)
		self.register_capability(
			"turn_on_device",
			lambda args: set_device_state(args, True),
		)
		self.register_capability(
			"turn_off_device",
			lambda args: set_device_state(args, False),
		)

		def get_status(args: dict) -> str:
			return json.dumps(mqtt.get_sensor_snapshot(), indent=2)

		self.register_capability(
			"get_sensor_status",
			get_status,
		)
