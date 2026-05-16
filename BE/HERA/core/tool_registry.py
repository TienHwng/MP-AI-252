"""Schema-only compatibility provider for LLM tool definitions.

Runtime execution is owned by ``runtime.ToolRunner``. This module only exposes
OpenAI-style schema definitions for older callers that still ask for a registry.
"""

from __future__ import annotations

from runtime.capability_registry import CapabilityRegistry


class ToolSchemaRegistry:
	"""Returns function schemas from the canonical capability registry."""

	def __init__(
		self,
		mqtt=None,
		*,
		capabilities: CapabilityRegistry | None = None,
		device_executor=None,
	) -> None:
		_ = mqtt, device_executor
		self.capabilities = capabilities or CapabilityRegistry()
		self.definitions = [
			self.capabilities.get_tool_definition(spec.name)
			for spec in self.capabilities.list_specs()
		]

	def get_definitions(self, names: list[str] | None = None) -> list[dict]:
		"""Return tool schemas, optionally filtered by name."""
		if names is None:
			return list(self.definitions)
		name_set = set(names)
		return [d for d in self.definitions if d["function"]["name"] in name_set]


ToolRegistry = ToolSchemaRegistry

__all__ = ["ToolRegistry", "ToolSchemaRegistry"]
