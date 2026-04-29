"""Device domain services and catalogs."""

from domain.devices.device_catalog import (
	DEVICE_STATUS_KEYS,
	DEVICE_TARGETS,
	DEVICE_TOOL_PARAMS,
	DEVICE_VALUE_SPECS,
	DEVICE_VALUE_TOOL_PARAMS,
	LIGHT_TARGETS,
	LIGHT_TOOL_PARAMS,
	SENSOR_VALUE_SPECS,
	SENSOR_VALUE_TOOL_PARAMS,
	coerce_device_value,
	coerce_sensor_value,
	get_device_value_spec,
	normalize_device_target,
	normalize_device_value_property,
	normalize_light_target,
	normalize_sensor_target,
)

__all__ = [
	"DEVICE_STATUS_KEYS",
	"DEVICE_TARGETS",
	"DEVICE_TOOL_PARAMS",
	"DEVICE_VALUE_SPECS",
	"DEVICE_VALUE_TOOL_PARAMS",
	"LIGHT_TARGETS",
	"LIGHT_TOOL_PARAMS",
	"SENSOR_VALUE_SPECS",
	"SENSOR_VALUE_TOOL_PARAMS",
	"coerce_device_value",
	"coerce_sensor_value",
	"get_device_value_spec",
	"normalize_device_target",
	"normalize_device_value_property",
	"normalize_light_target",
	"normalize_sensor_target",
]
