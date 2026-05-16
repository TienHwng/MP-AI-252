"""HTTP adapter for the HERA dashboard.

This keeps dashboard control actions on the same MQTT/runtime path as the
assistant instead of letting the React app simulate device state locally.
"""

from __future__ import annotations

import json
from typing import Any

from agents.orchestrator import Orchestrator
from aiohttp import web
from config import MODE, MQTT_BROKER, MQTT_PORT
from core.llm_service import LLMService
from core.logger import log_error
from core.message import MessageSource, UserMessage
from domain.devices import DEVICE_TARGETS, normalize_device_target
from main import (
	build_agents,
	build_memory_service,
	build_runtime,
	configure_logging,
	connect_mqtt,
	load_runtime_settings,
)
from runtime.execution_context import ExecutionContext
from schemas import ToolProposal

ALLOWED_SENSOR_WRITES = {
	"temperature",
	"humidity",
	"light",
	"gas",
	"gas_ppm",
	"gas_detected",
}


def jsonable(value: Any) -> Any:
	return json.loads(json.dumps(value, default=str, ensure_ascii=False))


@web.middleware
async def cors_middleware(request: web.Request, handler):
	if request.method == "OPTIONS":
		response = web.Response(status=204)
	else:
		response = await handler(request)
	response.headers["Access-Control-Allow-Origin"] = "*"
	response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	return response


def runtime_state(request: web.Request) -> dict[str, Any]:
	mqtt = request.app["mqtt"]
	device_executor = request.app["device_executor"]
	snapshot = mqtt.get_sensor_snapshot()
	return {
		"mode": MODE,
		"mqtt": {
			"broker": MQTT_BROKER,
			"port": MQTT_PORT,
			"connected": bool(getattr(mqtt.client, "is_connected", lambda: False)()),
		},
		"last_seen_at": snapshot.get("last_seen_at"),
		"source_topic": snapshot.get("source_topic"),
		"runtime": snapshot.get("runtime", {}),
		"devices": device_executor.get_device_status_report(),
		"sensors": mqtt.get_sensor_readings_snapshot(),
		"network": mqtt.get_network_snapshot(),
	}


async def handle_runtime_status(request: web.Request) -> web.Response:
	return web.json_response(jsonable(runtime_state(request)))


async def handle_device_status(request: web.Request) -> web.Response:
	device_executor = request.app["device_executor"]
	return web.json_response(
		jsonable(
			{
				"ok": True,
				"mode": MODE,
				**device_executor.get_runtime_state(),
			}
		)
	)


async def handle_set_device_state(request: web.Request) -> web.Response:
	target = normalize_device_target(request.match_info.get("target"))
	if target is None:
		return web.json_response(
			{
				"ok": False,
				"error": "invalid_device_target",
				"valid_targets": sorted(DEVICE_TARGETS),
			},
			status=400,
		)

	try:
		payload = await request.json()
	except json.JSONDecodeError:
		return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

	state = payload.get("state")
	if not isinstance(state, bool):
		return web.json_response(
			{"ok": False, "error": "state must be boolean"},
			status=400,
		)

	proposal = ToolProposal(
		capability_name="turn_on_device" if state else "turn_off_device",
		arguments={"device_target": target},
		rationale="Dashboard floorplan requested a device state change.",
		expected_outcome="MQTT telemetry reports the requested device state.",
		confidence=1.0,
	)
	context = ExecutionContext(
		request_id=str(payload.get("request_id") or "dashboard-control"),
		session_id=str(payload.get("session_id") or "dashboard"),
		user_id=str(payload.get("user_id") or "dashboard"),
		channel="dashboard",
		route_intent="device_control",
		specialist="dashboard_floorplan",
		metadata={"mode": MODE},
	)
	result = request.app["tool_runner"].run(proposal, context)
	status = 200 if result.ok else 409
	return web.json_response(jsonable(result.model_dump(mode="json")), status=status)


async def handle_get_model_settings(request: web.Request) -> web.Response:
	from core.runtime_settings import runtime_settings

	settings = runtime_settings.get()
	return web.json_response(
		jsonable(
			{
				"provider": settings.get("provider"),
				"models": settings.get("models", {}),
				"updatedAt": "",
			}
		)
	)


async def handle_update_model_settings(request: web.Request) -> web.Response:
	from core.runtime_settings import prune_settings, runtime_settings

	try:
		payload = await request.json()
	except Exception:
		return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

	pruned = prune_settings(payload)
	collection = runtime_settings.collection
	if collection is None:
		return web.json_response(
			{"ok": False, "error": "mongodb_unavailable"},
			status=503,
		)
	try:
		collection.update_one(
			{"_id": "hera_model_settings"},
			{"$set": {"provider": pruned["provider"], "models": pruned["models"]}},
			upsert=True,
		)
	except Exception as exc:
		return web.json_response({"ok": False, "error": str(exc)}, status=500)

	updated = runtime_settings.refresh_and_log()
	return web.json_response(
		jsonable(
			{
				"ok": True,
				"settings": {
					"provider": updated.get("provider"),
					"models": updated.get("models", {}),
					"updatedAt": "",
				},
			}
		)
	)


async def handle_rpc_command(request: web.Request) -> web.Response:

	try:
		payload = await request.json()
	except json.JSONDecodeError:
		return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

	method = payload.get("method")
	params = payload.get("params")

	if not method or params is None:
		return web.json_response(
			{"ok": False, "error": "method and params are required"},
			status=400,
		)

	request.app["mqtt"].publish_rpc(method, params)

	return web.json_response(
		{
			"ok": True,
			"message": f"Command '{method}' sent successfully",
			"method": method,
			"params": params,
		}
	)


async def handle_write_sensor_value(request: web.Request) -> web.Response:
	if MODE != "sim":
		return web.json_response(
			{
				"ok": False,
				"error": "sensor_write_requires_sim_mode",
				"mode": MODE,
			},
			status=409,
		)

	sensor = (request.match_info.get("sensor") or "").strip().lower()
	if sensor not in ALLOWED_SENSOR_WRITES:
		return web.json_response(
			{
				"ok": False,
				"error": "invalid_sensor",
				"valid_sensors": sorted(ALLOWED_SENSOR_WRITES),
			},
			status=400,
		)

	try:
		payload = await request.json()
	except json.JSONDecodeError:
		return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

	value = payload.get("value")
	if sensor == "gas_detected":
		if not isinstance(value, bool):
			return web.json_response(
				{"ok": False, "error": "gas_detected value must be boolean"},
				status=400,
			)
	elif isinstance(value, bool) or not isinstance(value, int | float):
		return web.json_response(
			{"ok": False, "error": "sensor value must be numeric"},
			status=400,
		)

	request.app["mqtt"].publish_rpc(
		"setSensorValue",
		{"sensor": sensor, "value": value},
	)
	return web.json_response(
		{
			"ok": True,
			"mode": MODE,
			"method": "setSensorValue",
			"params": {"sensor": sensor, "value": value},
		}
	)


async def handle_assistant_message(request: web.Request) -> web.Response:
	try:
		payload = await request.json()
	except json.JSONDecodeError:
		return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

	text = str(payload.get("text") or "").strip()
	if not text:
		return web.json_response({"ok": False, "error": "text is required"}, status=400)

	user_id = str(payload.get("user_id") or "dashboard")
	session_id = str(payload.get("session_id") or user_id)
	raw_source = str(payload.get("source") or "").strip().lower()
	source = (
		MessageSource.VOICE
		if raw_source == MessageSource.VOICE.value
		else MessageSource.REST
	)
	message = UserMessage(
		text=text,
		chat_id=f"dashboard:{session_id}",
		source=source,
		metadata={
			"user_id": user_id,
			"session_id": session_id,
			"mode": MODE,
			"input_modality": "voice" if source == MessageSource.VOICE else "text",
		},
	)
	try:
		response = await request.app["orchestrator"].handle(message)
	except Exception as exc:
		error_info = LLMService.describe_exception(exc)
		log_error(
			"Assistant request failed",
			data={
				"user": user_id,
				"session": message.chat_id,
				"status": error_info.get("status") or "unknown",
				"type": error_info["type"],
			},
			detail=LLMService.render_error_detail(error_info),
		)
		return web.json_response(
			jsonable(
				{
					"ok": False,
					"error": "assistant_runtime_error",
					"message": error_info["message"],
					"details": {
						"type": error_info["type"],
						"status": error_info.get("status"),
						"upstream": error_info.get("provider_name"),
						"is_byok": error_info.get("is_byok"),
					},
				}
			),
			status=502,
		)
	return web.json_response(
		jsonable(
			{
				"ok": True,
				"text": response.text,
				"agent_name": response.agent_name,
				"tools_used": response.tools_used,
				"confidence": response.confidence,
				"metadata": response.metadata,
				"source": source.value,
			}
		)
	)


async def cleanup(app: web.Application) -> None:
	mqtt = app.get("mqtt")
	if mqtt is not None:
		mqtt.disconnect()


def create_app() -> web.Application:
	configure_logging()
	settings, provider = load_runtime_settings()
	mqtt = connect_mqtt()
	if mqtt is None:
		raise RuntimeError("Cannot connect to MQTT broker for HERA dashboard API")

	llm = LLMService(provider)
	tool_registry, tool_runner = build_runtime(mqtt)
	memory_service = build_memory_service()
	agents = build_agents(llm, mqtt, tool_registry, tool_runner, memory_service)
	orchestrator = Orchestrator(
		llm,
		agents,
		mqtt,
		tool_runner=tool_runner,
		memory_service=memory_service,
		orchestrator_model=None,
	)

	app = web.Application(middlewares=[cors_middleware])
	app["settings"] = settings
	app["mqtt"] = mqtt
	app["tool_runner"] = tool_runner
	app["device_executor"] = tool_runner.device_executor
	app["orchestrator"] = orchestrator
	app.router.add_get("/api/runtime/status", handle_runtime_status)
	app.router.add_get("/api/devices/status", handle_device_status)
	app.router.add_post("/api/devices/{target}/state", handle_set_device_state)
	app.router.add_post("/api/sensors/{sensor}/value", handle_write_sensor_value)
	app.router.add_post("/api/rpc", handle_rpc_command)
	app.router.add_post("/api/assistant/message", handle_assistant_message)
	app.router.add_get("/api/settings/models", handle_get_model_settings)
	app.router.add_put("/api/settings/models", handle_update_model_settings)
	app.router.add_options("/{tail:.*}", lambda request: web.Response(status=204))
	app.on_cleanup.append(cleanup)
	return app


if __name__ == "__main__":
	web.run_app(create_app(), host="0.0.0.0", port=3002)
