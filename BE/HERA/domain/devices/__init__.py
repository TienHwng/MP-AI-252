"""Device domain services and catalogs."""

from domain.devices.device_catalog import (
	DEVICE_STATUS_KEYS,
	DEVICE_TARGETS,
	DEVICE_TOOL_PARAMS,
	LIGHT_TARGETS,
	LIGHT_TOOL_PARAMS,
	normalize_device_target,
	normalize_light_target,
)

__all__ = [
	"DEVICE_STATUS_KEYS",
	"DEVICE_TARGETS",
	"DEVICE_TOOL_PARAMS",
	"LIGHT_TARGETS",
	"LIGHT_TOOL_PARAMS",
	"normalize_device_target",
	"normalize_light_target",
]
