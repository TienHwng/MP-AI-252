import json
import os
import random
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV_PATH)


# =========================
# CONFIG
# =========================
def _env_bool(name: str, default: bool) -> bool:
	raw = os.getenv(name)
	if raw is None:
		return default
	return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
	raw = os.getenv(name)
	if raw is None:
		return default
	try:
		return int(raw.strip())
	except ValueError:
		return default


def _env_float(name: str, default: float) -> float:
	raw = os.getenv(name)
	if raw is None:
		return default
	try:
		return float(raw.strip())
	except ValueError:
		return default


RAW_MODE = (os.getenv("MODE", "sim") or "sim").strip().lower()
MODE = "sim" if RAW_MODE in {"sim", "simulator", "simulation"} else RAW_MODE
MQTT_SERVER = os.getenv("MQTT_BROKER")
MQTT_PORT = _env_int("MQTT_PORT", 1883)
COREIOT_TOKEN = os.getenv("COREIOT_TOKEN")

TOPIC_TELEMETRY = "v1/devices/me/telemetry"
TOPIC_RPC_REQUEST = "v1/devices/me/rpc/request/+"
TOPIC_RPC_RESPONSE_PREFIX = "v1/devices/me/rpc/response/"
TOPIC_ATTRIBUTES = "v1/devices/me/attributes"

CLIENT_ID = os.getenv("SIM_CLIENT_ID", "hera-sim-device")
TELEMETRY_INTERVAL = max(_env_int("SIM_TELEMETRY_INTERVAL", 2), 1)
SIM_ANOMALY_PROBABILITY = max(
	0.0,
	min(_env_float("SIM_ANOMALY_PROBABILITY", 0.1), 1.0),
)
SIM_GAS_DETECTED_THRESHOLD = _env_float("SIM_GAS_DETECTED_THRESHOLD", 300.0)
SIM_FAN_ON_SPEED = max(_env_int("SIM_FAN_ON_SPEED", 4095), 0)
SIM_DEFAULT_WS2812_BRIGHTNESS = max(
	0,
	min(_env_int("SIM_DEFAULT_WS2812_BRIGHTNESS", 10), 255),
)
SIM_DEFAULT_STRIP_BRIGHTNESS = max(
	0,
	min(_env_int("SIM_DEFAULT_STRIP_BRIGHTNESS", 10), 255),
)

# Optional direct DB persistence for running the simulator without HERA/MQTTManager.
# Keep this off by default to avoid duplicate rows when MQTTManager is already storing
# telemetry received from this simulator.
SIM_ENABLE_MONGODB = _env_bool("SIM_ENABLE_MONGODB", False)
TELEMETRY_DB_DEBUG = _env_bool("TELEMETRY_DB_DEBUG", False)
TELEMETRY_BUCKET_SECONDS = max(_env_int("TELEMETRY_BUCKET_SECONDS", 5), 1)
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "HERA")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "telemetry_points")

collection = None
devices_collection = None
persist_telemetry = SIM_ENABLE_MONGODB
telemetry_insert_count = 0

try:
	from pymongo import MongoClient
except ImportError:
	MongoClient = None


def floor_datetime_to_bucket(value: datetime) -> datetime:
	timestamp = int(value.timestamp())
	bucket_timestamp = timestamp - (timestamp % TELEMETRY_BUCKET_SECONDS)
	return datetime.fromtimestamp(bucket_timestamp, tz=UTC)


def connect_mongo_collections():
	if MongoClient is None:
		print(
			"[ WARNING ] Missing package 'pymongo'. "
			"Simulator still publishes MQTT telemetry; direct MongoDB writes are disabled."
		)
		return None, None

	try:
		mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=1500)
		mongo_client.admin.command("ping")
		db = mongo_client[MONGODB_DB]
		return db[MONGODB_COLLECTION], db["devices"]
	except Exception as e:
		print(
			f"[ WARNING ] Cannot connect MongoDB ({e}). "
			"Simulator still publishes MQTT telemetry; direct MongoDB writes are disabled."
		)
		return None, None


if SIM_ENABLE_MONGODB:
	collection, devices_collection = connect_mongo_collections()
	if collection is None or devices_collection is None:
		persist_telemetry = False


# =========================
# STATE
# =========================
running = True
state_lock = threading.Lock()
start_time = time.time()

device_state = {
	"led_status": False,
	"neo_led_status": False,
	"ws2812_status": False,
	"ws2812_brightness": SIM_DEFAULT_WS2812_BRIGHTNESS,
	"strip_brightness": SIM_DEFAULT_STRIP_BRIGHTNESS,
	"relay_status": False,
	"mini_fan_status": False,
	"fan_speed": 0,
}

sensor_state = {
	"temperature": 30.0,
	"humidity": 60.0,
	"light": 90.0,
	"gas": 80.0,
	"gas_detected": False,
}

network_state = {
	"wifi_connected": True,
	"wifi_rssi": _env_int("SIM_WIFI_RSSI_MIN", -55),
	"wifi_ip": os.getenv("SIM_WIFI_IP", "192.168.1.50"),
	"mqtt_connected": False,
}


# =========================
# HELPERS
# =========================
def uptime_ms() -> int:
	return int((time.time() - start_time) * 1000)


def pretty_json(data) -> str:
	return json.dumps(data, indent=2, ensure_ascii=False)


def clamp_int(value, minimum: int, maximum: int) -> int | None:
	if isinstance(value, bool) or not isinstance(value, int):
		return None
	return max(minimum, min(value, maximum))


def compute_anomaly_score() -> float:
	temp_component = (sensor_state["temperature"] - 30.0) / 10.0
	humidity_component = (sensor_state["humidity"] - 65.0) / 50.0
	gas_component = (sensor_state["gas"] - SIM_GAS_DETECTED_THRESHOLD) / 400.0
	return round(
		max(0.0, min(1.0, temp_component + humidity_component + gas_component)),
		3,
	)


def update_fake_sensor_data():
	temp_min = _env_float("SIM_TEMP_MIN", 27.0)
	temp_max = _env_float("SIM_TEMP_MAX", 34.0)
	humi_min = _env_float("SIM_HUMI_MIN", 55.0)
	humi_max = _env_float("SIM_HUMI_MAX", 82.0)
	light_min = _env_float("SIM_LIGHT_MIN", 80.0)
	light_max = _env_float("SIM_LIGHT_MAX", 650.0)
	gas_min = _env_float("SIM_GAS_MIN", 35.0)
	gas_max = _env_float("SIM_GAS_MAX", 180.0)
	gas_anomaly_min = _env_float("SIM_GAS_ANOMALY_MIN", 320.0)
	gas_anomaly_max = _env_float("SIM_GAS_ANOMALY_MAX", 650.0)
	rssi_min = _env_int("SIM_WIFI_RSSI_MIN", -70)
	rssi_max = _env_int("SIM_WIFI_RSSI_MAX", -42)

	with state_lock:
		is_anomaly_sample = random.random() < SIM_ANOMALY_PROBABILITY

		if is_anomaly_sample:
			sensor_state["temperature"] = round(
				random.uniform(max(36.0, temp_max), max(42.0, temp_max + 6.0)),
				2,
			)
			sensor_state["humidity"] = round(
				random.uniform(max(82.0, humi_max), max(95.0, humi_max + 10.0)),
				2,
			)
		else:
			normal_temp_max = min(temp_max, 30.0)
			normal_humi_max = min(humi_max, 65.0)
			sensor_state["temperature"] = round(
				random.uniform(temp_min, max(temp_min, normal_temp_max)),
				2,
			)
			sensor_state["humidity"] = round(
				random.uniform(humi_min, max(humi_min, normal_humi_max)),
				2,
			)

		sensor_state["light"] = round(random.uniform(light_min, light_max), 2)
		if is_anomaly_sample:
			sensor_state["gas"] = round(
				random.uniform(
					max(gas_anomaly_min, gas_max),
					max(gas_anomaly_max, gas_anomaly_min),
				),
				2,
			)
		else:
			sensor_state["gas"] = round(random.uniform(gas_min, gas_max), 2)
		sensor_state["gas_detected"] = sensor_state["gas"] >= SIM_GAS_DETECTED_THRESHOLD
		network_state["wifi_rssi"] = random.randint(rssi_min, rssi_max)


def persist_telemetry_payload(payload: dict):
	global persist_telemetry, telemetry_insert_count

	if not persist_telemetry or collection is None or devices_collection is None:
		return

	try:
		observed_at = datetime.now(UTC)
		current_user_id = None
		try:
			device_info = devices_collection.find_one({"device_id": "device_0001"})
			if device_info:
				current_user_id = device_info.get("current_user_id")
		except Exception as e:
			print(f"[ WARNING ] Could not fetch device owner: {e}")

		doc = {
			"recorded_at": observed_at,
			"chart_recorded_at": floor_datetime_to_bucket(observed_at),
			"metadata": {
				"device_id": "device_0001",
				"env_id": "env_0001",
				"user_id": current_user_id,
				"telemetry_bucket_seconds": TELEMETRY_BUCKET_SECONDS,
				"source": "mqtt_simulator",
			},
			**payload,
			"last_seen_at": observed_at.isoformat(),
			"source_topic": TOPIC_TELEMETRY,
		}
		collection.insert_one(doc)
		telemetry_insert_count += 1
		if TELEMETRY_DB_DEBUG or telemetry_insert_count == 1:
			print(
				"[ INFO ] [Database] Inserted simulator telemetry "
				f"#{telemetry_insert_count} "
				f"user_id={current_user_id or 'unclaimed'}"
			)
	except Exception as e:
		print(
			f"[ WARNING ] MongoDB write failed ({e}). "
			"Simulator keeps publishing MQTT telemetry; direct persistence is disabled."
		)
		persist_telemetry = False


# =========================
# MQTT CALLBACKS
# =========================
def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties=None):
	with state_lock:
		network_state["mqtt_connected"] = reason_code == 0

	if reason_code == 0:
		print("[MQTT] Connected successfully")
		client.subscribe(TOPIC_RPC_REQUEST)
		print(f"[MQTT] Subscribed: {TOPIC_RPC_REQUEST}")
	else:
		print(f"[MQTT] Connect failed, reason_code={reason_code}")


def on_disconnect(client: mqtt.Client, userdata, *args):
	with state_lock:
		network_state["mqtt_connected"] = False
	reason_code = args[-2] if len(args) >= 2 else args[0] if args else None
	print(f"[MQTT] Disconnected, reason_code={reason_code}")


def on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
	topic = msg.topic
	payload_raw = msg.payload.decode("utf-8", errors="ignore")

	print(f"[MQTT] Received topic: {topic}")
	try:
		data = json.loads(payload_raw)
		print("[MQTT] Payload pretty:")
		print(pretty_json(data))
	except json.JSONDecodeError:
		print(f"[MQTT] Payload raw: {payload_raw}")
		print("[MQTT] Error JSON!")
		return

	method = data.get("method")
	params = data.get("params")

	request_id = topic.split("/")[-1]
	response = {}

	with state_lock:
		if method == "setValueLedBlinky":
			if not isinstance(params, bool):
				response["error"] = "params must be bool"
			else:
				device_state["led_status"] = params
				print(
					"[ACTION] Turning on normal LED"
					if params
					else "[ACTION] Turning off normal LED"
				)
				response["LedState"] = params

		elif method == "setValueNeoLed":
			if not isinstance(params, bool):
				response["error"] = "params must be bool"
			else:
				device_state["neo_led_status"] = params
				print(
					"[ACTION] Turning on NeoPixel"
					if params
					else "[ACTION] Turning off NeoPixel"
				)
				response["NeoLedState"] = params

		elif method == "setValueWS2812":
			if not isinstance(params, bool):
				response["error"] = "params must be bool"
			else:
				device_state["ws2812_status"] = params
				if params and device_state["ws2812_brightness"] <= 0:
					device_state["ws2812_brightness"] = SIM_DEFAULT_WS2812_BRIGHTNESS
				print(
					"[ACTION] Turning on WS2812"
					if params
					else "[ACTION] Turning off WS2812"
				)
				response["WS2812State"] = params

		elif method == "setValueRelay":
			if not isinstance(params, bool):
				response["error"] = "params must be bool"
			else:
				device_state["relay_status"] = params
				print(
					"[ACTION] Turning on Relay"
					if params
					else "[ACTION] Turning off Relay"
				)
				response["RelayState"] = params

		elif method == "setValueMiniFan":
			if not isinstance(params, bool):
				response["error"] = "params must be bool"
			else:
				device_state["mini_fan_status"] = params
				device_state["fan_speed"] = SIM_FAN_ON_SPEED if params else 0
				print(
					"[ACTION] Turning on Fan" if params else "[ACTION] Turning off Fan"
				)
				response["FanState"] = params
				response["FanSpeed"] = device_state["fan_speed"]

		elif method == "setWS2812Brightness":
			value = clamp_int(params, 0, 255)
			if value is None:
				response["error"] = "params must be int (0..255)"
			else:
				device_state["ws2812_brightness"] = value
				device_state["ws2812_status"] = value > 0
				print(f"[ACTION] WS2812 brightness -> {value}")
				response["WS2812_Brightness"] = value
				response["WS2812State"] = device_state["ws2812_status"]

		elif method == "setStripBrightness":
			value = clamp_int(params, 0, 255)
			if value is None:
				response["error"] = "params must be int (0..255)"
			else:
				device_state["strip_brightness"] = value
				print(f"[ACTION] Strip brightness -> {value}")
				response["Strip_Brightness"] = value

		elif method == "setFanSpeed":
			value = clamp_int(params, 0, 4095)
			if value is None:
				response["error"] = "params must be int (0..4095)"
			else:
				device_state["fan_speed"] = value
				device_state["mini_fan_status"] = value > 0
				print(f"[ACTION] Fan speed -> {value}")
				response["Fan_Speed"] = value
				response["Fan_Status"] = device_state["mini_fan_status"]

		else:
			print(f"[MQTT] Unknown method: {method}")
			response["error"] = "Unknown method"

	response_topic = f"{TOPIC_RPC_RESPONSE_PREFIX}{request_id}"
	response_payload = pretty_json(response)

	client.publish(response_topic, response_payload)
	client.publish(TOPIC_ATTRIBUTES, response_payload)

	print(f"[MQTT] Response -> {response_topic}")
	print(response_payload)
	print(f"[MQTT] Attributes -> {TOPIC_ATTRIBUTES}")
	print(response_payload)


# =========================
# TELEMETRY
# =========================
def build_telemetry_payload():
	with state_lock:
		payload = {
			"network": {
				"wifi_connected": network_state["wifi_connected"],
				"wifi_rssi": network_state["wifi_rssi"],
				"wifi_ip": network_state["wifi_ip"],
				"mqtt_connected": network_state["mqtt_connected"],
				"uptime_ms": uptime_ms(),
			},
			"devices": {
				"led": {
					"status": device_state["led_status"],
					"brightness": 255,
					"voltage": 3.3,
				},
				"neo_led": {
					"status": device_state["neo_led_status"],
					"brightness": device_state["strip_brightness"],
					"color": "#FF0000",
					"voltage": 5.0,
				},
				"ws2812": {
					"status": device_state["ws2812_status"],
					"brightness": device_state["ws2812_brightness"],
					"color": "#00FF00",
					"voltage": 5.0,
				},
				"relay": {
					"status": device_state["relay_status"],
					"voltage": 5.0,
				},
				"mini_fan": {
					"status": device_state["mini_fan_status"],
					"speed": device_state["fan_speed"],
					"voltage": 5.0,
				},
			},
			"sensors": {
				"dht20": {
					"temperature": sensor_state["temperature"],
					"humidity": sensor_state["humidity"],
					"voltage": 3.3,
				},
				"light": {
					"value": sensor_state["light"],
					"voltage": 3.3,
				},
				"gas": {
					"value": sensor_state["gas"],
					"voltage": 3.3,
				},
			},
		}
	return payload


def publish_telemetry_loop(client: mqtt.Client):
	global running

	while running:
		update_fake_sensor_data()
		payload = build_telemetry_payload()
		payload_str = pretty_json(payload)

		result = client.publish(TOPIC_TELEMETRY, payload_str)
		if result.rc == mqtt.MQTT_ERR_SUCCESS:
			print(f"[MQTT] Send topic: {TOPIC_TELEMETRY}")
			print(payload_str)
			persist_telemetry_payload(payload)
		else:
			print(f"[MQTT] Publish failed, rc={result.rc}")

		time.sleep(TELEMETRY_INTERVAL)


# =========================
# MAIN
# =========================
def build_client() -> mqtt.Client:
	client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311)
	if COREIOT_TOKEN:
		client.username_pw_set(COREIOT_TOKEN)

	client.on_connect = on_connect
	client.on_disconnect = on_disconnect
	client.on_message = on_message

	return client


def main():
	global running

	client = build_client()

	if MODE != "sim":
		raise RuntimeError(
			f"mqtt_simulator.py is only allowed when MODE=sim. Current MODE={RAW_MODE!r}"
		)
	if not MQTT_SERVER:
		raise RuntimeError("MQTT_BROKER is not configured in .env")

	print(f"[SIM] MODE=sim; connecting fake hardware to {MQTT_SERVER}:{MQTT_PORT} ...")
	client.connect(MQTT_SERVER, MQTT_PORT, keepalive=60)

	telemetry_thread = threading.Thread(
		target=publish_telemetry_loop,
		args=(client,),
		daemon=True,
	)
	telemetry_thread.start()

	try:
		client.loop_forever()
	except KeyboardInterrupt:
		print("\n[APP] Stopping simulator...")
		running = False
		client.disconnect()


if __name__ == "__main__":
	main()
