import sys
from pathlib import Path

# Must setup sys.path BEFORE importing from BE
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.append(str(PROJECT_ROOT))

import asyncio
import copy
import json
import os
import random
import re
import threading
import time
from datetime import UTC, datetime


import paho.mqtt.client as mqtt
from amqtt.broker import Broker

# Enable ANSI color support on Windows PowerShell/CMD
if os.name == "nt":
	os.system("color")


# Color class for basic terminal colors
class Color:
	CYAN = "\033[96m"
	GREEN = "\033[92m"
	YELLOW = "\033[93m"
	BLUE = "\033[94m"
	MAGENTA = "\033[95m"
	RED = "\033[91m"
	BOLD = "\033[1m"
	RESET = "\033[0m"


from BE.HERA.config import (
	MODE,
	MQTT_BROKER,
	MQTT_BROKER_BIND_HOST,
	MQTT_PORT,
	MQTT_RPC_REQUEST_TOPIC_PREFIX,
	MQTT_SUBSCRIBE_TOPIC,
)


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


ENABLE_MONGODB = _env_bool("MQTT_ENABLE_MONGODB", False)
TELEMETRY_DB_DEBUG = _env_bool("TELEMETRY_DB_DEBUG", False)
TELEMETRY_BUCKET_SECONDS = max(_env_int("TELEMETRY_BUCKET_SECONDS", 5), 1)
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "HERA")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "telemetry_points")

collection = None
devices_collection = None

try:
	from pymongo import MongoClient
except ImportError:
	MongoClient = None


def connect_mongo_collections():
	if MongoClient is None:
		print(
			"[ WARNING ] Missing 'pymongo' package. "
			"MQTT will continue to run, only telemetry persistence to MongoDB is disabled."
		)
		return None, None

	try:
		mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=1500)
		# Ping to fail-fast if MongoDB is not running locally
		mongo_client.admin.command("ping")
		db = mongo_client[MONGODB_DB]
		return db[MONGODB_COLLECTION], db["devices"]
	except Exception as e:
		print(
			f"[ WARNING ] Cannot connect to MongoDB ({e}). "
			"MQTT will continue to run, only telemetry persistence to MongoDB is disabled."
		)
		return None, None


if ENABLE_MONGODB:
	collection, devices_collection = connect_mongo_collections()


def floor_datetime_to_bucket(value: datetime) -> datetime:
	timestamp = int(value.timestamp())
	bucket_timestamp = timestamp - (timestamp % TELEMETRY_BUCKET_SECONDS)
	return datetime.fromtimestamp(bucket_timestamp, tz=UTC)


# Helper function to parse color input for WS2812 - supports both hex (#RRGGBB) and RGB (r,g,b) formats
def parse_ws2812_color_input(color_input):
	color_input = color_input.strip()

	# Allow hex input formats: #FF00AA, FF00AA, 0xFF00AA
	if color_input.startswith("#") or color_input.startswith("0x") or color_input.startswith("0X"):
		return color_input

	# Allow RGB input format: 255,111,222
	parts = color_input.split(",")

	if len(parts) != 3:
		raise ValueError("RGB must be in format: 255,111,222")

	r = int(parts[0].strip())
	g = int(parts[1].strip())
	b = int(parts[2].strip())

	if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
		raise ValueError("RGB values must be from 0 to 255")

	return {
		"r": r,
		"g": g,
		"b": b
	}


# === Terminal menu helpers ===
ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
menu_inner_width = 70

def visible_len(text: str) -> int:
	"""Return text length without ANSI color escape codes."""
	return len(ansi_escape.sub("", text))


def pad_visible(text: str, width: int) -> str:
	"""Pad text based on visible length, ignoring ANSI color codes."""
	return text + " " * max(width - visible_len(text), 0)


def menu_border(left: str, fill: str, right: str) -> str:
	return f"{Color.CYAN}{left}{fill * menu_inner_width}{right}"


def menu_line(content: str = "") -> str:
	return (
		f"{Color.CYAN}║"
		f"{pad_visible(content, menu_inner_width)}"
		f"{Color.CYAN}║"
	)


def menu_section(title: str, color: str) -> str:
	return menu_line(f" {color}[ {title} ]{Color.CYAN}")


def menu_option(number: int, label: str, color: str) -> str:
	return f"{color}{number:>2}.{Color.RESET} {label}"


def menu_row(left: str, right: str = "") -> str:
	left_column_width = 32

	if right:
		content = (
			"   "
			+ pad_visible(left, left_column_width)
			+ " "
			+ right
		)
	else:
		content = "   " + left

	return menu_line(content)


class MQTTManager:
	def __init__(
		self,
		broker_address=None,
		port=None,
		broker_bind_host=None,
		*,
		persist_telemetry: bool | None = None,
	):
		self.broker_address = broker_address or MQTT_BROKER
		self.port = port if port is not None else MQTT_PORT
		self.broker_bind_host = broker_bind_host or MQTT_BROKER_BIND_HOST
		self.persist_telemetry = (
			ENABLE_MONGODB if persist_telemetry is None else bool(persist_telemetry)
		)
		self.collection = collection
		self.devices_collection = devices_collection
		if self.persist_telemetry and (
			self.collection is None or self.devices_collection is None
		):
			self.collection, self.devices_collection = connect_mongo_collections()

		if self.persist_telemetry and self.collection is None:
			print(
				"[ INFO ] Telemetry persistence disabled. "
				"Application still receives MQTT data normally."
			)

		# Broker configuration
		self.broker_config = {
			"listeners": {
				"default": {
					"type": "tcp",
					"bind": f"{self.broker_bind_host}:{self.port}",
				}
			},
			"plugins": {
				"amqtt.plugins.authentication.AnonymousAuthPlugin": {},
				"amqtt.plugins.topic_checking.TopicTabooPlugin": {},
				"amqtt.plugins.sys.broker.BrokerSysPlugin": {"sys_interval": 10},
			},
		}

		# Broker configuration
		self.broker_config = {
			"listeners": {
				"default": {
					"type": "tcp",
					"bind": f"{self.broker_bind_host}:{self.port}",
				}
			},
			"plugins": {
				"amqtt.plugins.authentication.AnonymousAuthPlugin": {},
				"amqtt.plugins.topic_checking.TopicTabooPlugin": {},
				"amqtt.plugins.sys.broker.BrokerSysPlugin": {"sys_interval": 10},
			},
		}

		# Initialize Client
		self.client = mqtt.Client()
		# Attach callback functions
		self.client.on_connect = self.on_connect
		self.client.on_message = self.on_message
		self.client.on_subscribe = self.on_subscribe
		self.client.on_publish = self.on_publish
		self.latest_sensor_data = {}
		self.telemetry_insert_count = 0
		# self.latest_sensor_data = {"temperature": "25"}

	@staticmethod
	def _mapping(value: object) -> dict:
		return value if isinstance(value, dict) else {}

	@staticmethod
	def _first_present(*values):
		for value in values:
			if value is not None:
				return value
		return None

	@classmethod
	def _scalar_value(cls, value):
		if isinstance(value, dict):
			return value.get("value")
		return value

	@classmethod
	def _number_value(cls, value):
		value = cls._scalar_value(value)
		if isinstance(value, bool) or value is None:
			return None
		if isinstance(value, int | float):
			return value
		if isinstance(value, str):
			try:
				return float(value.strip())
			except ValueError:
				return None
		return None

	@classmethod
	def _bool_value(cls, value):
		value = cls._scalar_value(value)
		if isinstance(value, bool):
			return value
		if isinstance(value, int | float):
			if value == 1:
				return True
			if value == 0:
				return False
		if isinstance(value, str):
			normalized = value.strip().lower()
			if normalized in {"1", "true", "on", "active"}:
				return True
			if normalized in {"0", "false", "off", "inactive"}:
				return False
		return None

	@classmethod
	def _normalize_sensor_payload(cls, payload: dict) -> dict:
		if not isinstance(payload, dict):
			return {}

		network = cls._mapping(payload.get("network"))
		devices = cls._mapping(payload.get("devices"))
		sensors = cls._mapping(payload.get("sensors"))
		dht20 = cls._mapping(cls._first_present(sensors.get("dht20"), sensors.get("dht")))
		led = cls._mapping(devices.get("led"))
		neo_led = cls._mapping(cls._first_present(devices.get("neo_led"), devices.get("neo")))
		ws2812 = cls._mapping(devices.get("ws2812"))
		relay = cls._mapping(devices.get("relay"))
		mini_fan = cls._mapping(cls._first_present(devices.get("mini_fan"), devices.get("fan")))
		gas = cls._mapping(sensors.get("gas"))

		return {
			"network": {
				"wifi_connected": cls._bool_value(
					cls._first_present(network.get("wifi_connected"), payload.get("wifi_connected"))
				),
				"wifi_rssi": cls._number_value(
					cls._first_present(network.get("wifi_rssi"), payload.get("wifi_rssi"))
				),
				"wifi_ip": cls._first_present(network.get("wifi_ip"), payload.get("wifi_ip")),
				"mqtt_connected": cls._bool_value(
					cls._first_present(network.get("mqtt_connected"), payload.get("mqtt_connected"))
				),
				"uptime_ms": cls._number_value(
					cls._first_present(network.get("uptime_ms"), payload.get("uptime_ms"))
				),
			},
			"devices": {
				"led": {
					**led,
					"status": cls._bool_value(
						cls._first_present(
							led.get("status"),
							devices.get("led_status"),
							payload.get("led_state"),
						)
					),
					"brightness": cls._number_value(led.get("brightness")),
					"voltage": cls._number_value(led.get("voltage")),
				},
				"neo_led": {
					**neo_led,
					"status": cls._bool_value(
						cls._first_present(
							neo_led.get("status"),
							devices.get("neo_led_status"),
							payload.get("neo_led_state"),
						)
					),
					"brightness": cls._number_value(
						cls._first_present(neo_led.get("brightness"), devices.get("strip_brightness"))
					),
					"color": cls._first_present(neo_led.get("color"), devices.get("neo_led_color")),
					"voltage": cls._number_value(neo_led.get("voltage")),
				},
				"ws2812": {
					**ws2812,
					"status": cls._bool_value(
						cls._first_present(ws2812.get("status"), devices.get("ws2812_status"))
					),
					"brightness": cls._number_value(
						cls._first_present(ws2812.get("brightness"), devices.get("ws2812_brightness"))
					),
					"color": ws2812.get("color"),
					"voltage": cls._number_value(ws2812.get("voltage")),
				},
				"relay": {
					**relay,
					"status": cls._bool_value(
						cls._first_present(relay.get("status"), devices.get("relay_status"))
					),
					"voltage": cls._number_value(relay.get("voltage")),
				},
				"mini_fan": {
					**mini_fan,
					"status": cls._bool_value(
						cls._first_present(mini_fan.get("status"), devices.get("mini_fan_status"))
					),
					"speed": cls._number_value(
						cls._first_present(mini_fan.get("speed"), devices.get("fan_speed"))
					),
					"voltage": cls._number_value(mini_fan.get("voltage")),
				},
			},
			"sensors": {
				"dht20": {
					**dht20,
					"temperature": cls._number_value(
						cls._first_present(
							dht20.get("temperature"),
							sensors.get("temperature"),
							payload.get("temperature"),
							payload.get("temp"),
						)
					),
					"humidity": cls._number_value(
						cls._first_present(
							dht20.get("humidity"),
							sensors.get("humidity"),
							payload.get("humidity"),
							payload.get("humi"),
						)
					),
					"voltage": cls._number_value(dht20.get("voltage")),
				},
				"light": {
					**cls._mapping(sensors.get("light")),
					"value": cls._number_value(
						cls._first_present(sensors.get("light"), payload.get("light"), payload.get("lux"))
					),
					"voltage": cls._number_value(cls._mapping(sensors.get("light")).get("voltage")),
				},
				"gas": {
					**gas,
					"value": cls._number_value(
						cls._first_present(
							gas.get("value"),
							sensors.get("gas"),
							sensors.get("gas_ppm"),
							payload.get("gas_ppm"),
							payload.get("gasPpm"),
							payload.get("gas"),
						)
					),
					"detected": cls._bool_value(
						cls._first_present(
							gas.get("detected"),
							gas.get("gas_detected"),
							sensors.get("gas_detected"),
							payload.get("gas_detected"),
							payload.get("gasDetected"),
						)
					),
					"voltage": cls._number_value(gas.get("voltage")),
				},
			},
		}

	@property
	def sensor_state(self) -> dict:
		"""Compatibility property - returns latest_sensor_data"""
		return self.latest_sensor_data

	# --- Broker functions ---
	def _start_broker_thread(self):
		async def broker_coro():
			broker = Broker(self.broker_config)
			await broker.start()
			print("[ OK ] MQTT Broker started...")

		# Each thread needs its own event loop for asyncio
		loop = asyncio.new_event_loop()
		asyncio.set_event_loop(loop)
		loop.run_until_complete(broker_coro())
		loop.run_forever()

	# --- Client callback functions ---
	def on_connect(self, client, userdata, flags, rc):
		client.subscribe(MQTT_SUBSCRIBE_TOPIC, qos=0)
		# Upon connection, subscribe to all topics (#)
		# print("[ OK ] Client Connected.")

	def on_subscribe(self, client, userdata, mid, granted_qos):
		# Do smth ?
		# print("[ OK ] Subscribed successfully.")
		pass

	def on_message(self, client, userdata, msg):
		topic = msg.topic
		payload = msg.payload.decode("utf-8")

		if "telemetry" in topic:
			# Log sensor data received from ESP32 (for debugging)
			# print(f"[ INFO ] [Sensor data] {payload}")
			try:
				parsed = json.loads(payload)
				observed_at = datetime.now(UTC)
				chart_recorded_at = floor_datetime_to_bucket(observed_at)
				self.latest_sensor_data = self._normalize_sensor_payload(parsed)
				self.latest_sensor_data["last_seen_at"] = observed_at.isoformat()
				self.latest_sensor_data["source_topic"] = topic
				self.latest_sensor_data["runtime"] = {
					"mode": MODE,
					"source": "mqtt",
					"source_kind": "sim" if MODE == "sim" else "real",
				}

				if (
					self.persist_telemetry
					and self.collection is not None
					and self.devices_collection is not None
				):
					try:
						current_user_id = None
						try:
							device_info = self.devices_collection.find_one(
								{"device_id": "device_0001"}
							)
							if device_info:
								current_user_id = device_info.get("current_user_id")
						except Exception as e:
							print(f"[ WARNING ] Could not fetch device owner: {e}")

						doc = {
							"recorded_at": observed_at,
							"chart_recorded_at": chart_recorded_at,
							"metadata": {
								"device_id": "device_0001",
								"env_id": "env_0001",
								"user_id": current_user_id,
								"telemetry_bucket_seconds": TELEMETRY_BUCKET_SECONDS,
								"source": "mqtt_manager",
								"mode": MODE,
							},
							**{
								k: v
								for k, v in self.latest_sensor_data.items()
								if v is not None
							},
						}

						self.collection.insert_one(doc)
						self.telemetry_insert_count += 1
						if TELEMETRY_DB_DEBUG or self.telemetry_insert_count == 1:
							print(
								"[ INFO ] [Database] Inserted telemetry "
								f"#{self.telemetry_insert_count} "
								f"user_id={current_user_id or 'unclaimed'}"
							)
					except Exception as e:
						print(
							f"[ WARNING ] MongoDB write failed ({e}). "
							"MQTT will continue running, telemetry persistence is temporarily disabled."
						)
						self.persist_telemetry = False

			except Exception as e:
				print("JSON parse error:", e)

		elif "response" in topic:
			print(f"[ OK ] [Feedback circuit] Topic: {topic} | Data: {payload}")
		else:
			pass

	def on_publish(self, client, userdata, mid):
		print(f"[ INFO ] Message ID {mid} published successfully")

	# --- Control functions (API for other files to call) ---
	def start(self):
		"""Start Broker in hidden thread and connect Client"""
		# Run Broker in separate thread to avoid blocking main program
		broker_thread = threading.Thread(target=self._start_broker_thread, daemon=True)
		broker_thread.start()

		# Wait briefly for Broker to start
		time.sleep(2)

		# Connect Client to Broker
		self.client.connect(self.broker_address, self.port)

		# Use loop_start() to run in background instead of loop_forever() to avoid blocking main thread
		self.client.loop_start()

	def connect_client_only(self):
		"""Chỉ kết nối MQTT client, không tự chạy broker nội bộ."""
		self.client.connect(self.broker_address, self.port)
		self.client.loop_start()

	# Alias for HERA compatibility
	def connect(self):
		"""Alias for start() - used by HERA"""
		self.start()

	def disconnect(self):
		"""Disconnect MQTT client"""
		if self.client:
			self.client.loop_stop()
			self.client.disconnect()
			print("[ INFO ] MQTT Client disconnected")

	def send_rpc_command(self, method_name, params):
		"""Send commands to ESP32 via MQTT with JSON encoding"""
		request_id = random.randint(1, 10000)  # Generate random ID for each request
		topic = f"{MQTT_RPC_REQUEST_TOPIC_PREFIX}/{request_id}"

		# Encode data as JSON
		payload = {"method": method_name, "params": params}
		json_payload = json.dumps(payload)

		# Publish to MQTT
		self.client.publish(topic, json_payload)
		print(f"[ INFO ] [Backend Send] Topic: {topic} | Data: {json_payload}")

	# Alias for HERA compatibility
	def publish_rpc(self, method: str, params):
		"""Alias for send_rpc_command() - used by HERA"""
		self.send_rpc_command(method, params)

	def get_sensor_snapshot(self) -> dict:
		"""Return a copy of the current sensor state - used by HERA"""
		return copy.deepcopy(self.latest_sensor_data)

	def get_device_snapshot(self) -> dict:
		"""Return a copy of the latest device states."""
		return copy.deepcopy(self.latest_sensor_data.get("devices", {}))

	def get_network_snapshot(self) -> dict:
		"""Return a copy of the latest network state."""
		return copy.deepcopy(self.latest_sensor_data.get("network", {}))

	def get_sensor_readings_snapshot(self) -> dict:
		"""Return a copy of the latest physical sensor readings."""
		return copy.deepcopy(self.latest_sensor_data.get("sensors", {}))


# === How to run this file for testing ===
if __name__ == "__main__":
	mqtt_system = MQTTManager()
	mqtt_system.start()

	print("HERA is ready. Enter a command (type 'exit' to quit):")

	try:
		while True:
			# === Render main terminal menu ===
			menu_lines = [
				# === Header ===
				menu_border("╔", "═", "╗"),
				menu_line(
					f"                     {Color.BOLD}H.E.R.A. CONTROL CENTER{Color.RESET}"
				),
				menu_border("╠", "═", "╣"),

				# === Section 1: Lighting controls ===
				menu_section("LIGHTING CONTROLS", Color.YELLOW),
				menu_row(
					menu_option(1, "Turn ON living room light", Color.YELLOW),
					menu_option(2, "Turn OFF living room light", Color.YELLOW),
				),
				menu_row(
					menu_option(3, "Turn ON NeoPixel light", Color.YELLOW),
					menu_option(4, "Turn OFF NeoPixel light", Color.YELLOW),
				),
				menu_row(
					menu_option(5, "Set NeoPixel Brightness", Color.YELLOW),
				),
				menu_row(
					menu_option(6, "Turn ON WS2812 light", Color.YELLOW),
					menu_option(7, "Turn OFF WS2812 light", Color.YELLOW),
				),
				menu_row(
					menu_option(8, "Set WS2812 Brightness", Color.YELLOW),
					menu_option(9, "Set WS2812 Color", Color.YELLOW),
				),
				menu_border("╟", "─", "╢"),

				# === Section 2: Device controls ===
				menu_section("DEVICE CONTROLS", Color.BLUE),
				menu_row(
					menu_option(10, "Turn ON mini fan", Color.BLUE),
					menu_option(11, "Turn OFF mini fan", Color.BLUE),
				),
				menu_row(
					menu_option(12, f"Set Fan Speed (0-{2**10 - 1})", Color.BLUE),
				),
				menu_row(
					menu_option(13, "Turn ON relay", Color.BLUE),
					menu_option(14, "Turn OFF relay", Color.BLUE),
				),
				menu_border("╟", "─", "╢"),

				# === Section 3: System monitoring ===
				menu_section("SYSTEM MONITORING", Color.MAGENTA),
				menu_row(
					menu_option(15, "View sensors status", Color.MAGENTA),
					menu_option(16, "View devices status", Color.MAGENTA),
				),
				menu_row(
					menu_option(17, "View network status", Color.MAGENTA),
					menu_option(18, "View full telemetry data", Color.MAGENTA),
				),
				menu_border("╟", "─", "╢"),

				# === Exit option ===
				menu_row(menu_option(0, "Exit program", Color.RED)),
				menu_border("╚", "═", "╝"),
			]

			print("\n" + "\n".join(menu_lines) + Color.RESET)

			# Get user's choice
			choice = input(
				f"{Color.BOLD} [ INPUT ] Please choose an option (0-18): {Color.RESET}"
			).strip()

			if choice == "0":
				print(
					Color.RED
					+ "\nExiting H.E.R.A. Control Center. Goodbye!\n"
					+ Color.RESET
				)
				break # Keep your break logic

			elif choice == "1":
				print(
					Color.GREEN
					+ "\n>>> HERA: Turning on the living room light..."
					+ Color.RESET
				)
				mqtt_system.send_rpc_command("setValueLedBlinky", True)

			elif choice == "2":
				print(
					Color.YELLOW
					+ "\n>>> HERA: Turning off the living room light..."
					+ Color.RESET
				)
				mqtt_system.send_rpc_command("setValueLedBlinky", False)

			elif choice == "3":
				print(
					Color.GREEN
					+ "\n>>> HERA: Turning on the NeoPixel light..."
					+ Color.RESET
				)
				mqtt_system.send_rpc_command("setValueNeoLed", True)

			elif choice == "4":
				print(
					Color.YELLOW
					+ "\n>>> HERA: Turning off the NeoPixel light..."
					+ Color.RESET
				)
				mqtt_system.send_rpc_command("setValueNeoLed", False)

			elif choice == "5":
				print(
					Color.GREEN
					+ "\n>>> HERA: Setting NeoPixel brightness..."
					+ Color.RESET
				)
				try:
					val = int(
						input(
							Color.YELLOW
							+ "Enter NeoPixel Brightness (0-255): "
							+ Color.RESET
						).strip()
					)
					mqtt_system.send_rpc_command("setStripBrightness", val)
				except ValueError:
					print(Color.RED + "Invalid input. Please enter a number." + Color.RESET)

			elif choice == "6":
				print(Color.GREEN + "\n>>> HERA: Turning on WS2812 light..." + Color.RESET)
				mqtt_system.send_rpc_command("setValueWS2812", True)

			elif choice == "7":
				print(Color.YELLOW + "\n>>> HERA: Turning off WS2812 light..." + Color.RESET)
				mqtt_system.send_rpc_command("setValueWS2812", False)

			elif choice == "8":
				print(Color.GREEN + "\n>>> HERA: Setting WS2812 brightness..." + Color.RESET)
				try:
					val = int(
						input(
							Color.YELLOW
							+ "Enter WS2812 Brightness (0-255): "
							+ Color.RESET
						).strip()
					)
					mqtt_system.send_rpc_command("setWS2812Brightness", val)
				except ValueError:
					print(Color.RED + "Invalid input. Please enter a number." + Color.RESET)

			elif choice == "9":
				print(Color.YELLOW + "\n>>> HERA: Setting WS2812 color..." + Color.RESET)
				try:
					color_input = input(
						Color.MAGENTA
						+ "Enter WS2812 color (#RRGGBB or r,g,b): "
						+ Color.RESET
					).strip()

					color_data = parse_ws2812_color_input(color_input)
					mqtt_system.send_rpc_command("setWS2812Color", color_data)

				except Exception as e:
					print(Color.RED + f"Invalid color input: {e}" + Color.RESET)

			elif choice == "10":
				print(Color.GREEN + "\n>>> HERA: Turning on mini fan..." + Color.RESET)
				mqtt_system.send_rpc_command("setValueMiniFan", True)

			elif choice == "11":
				print(Color.YELLOW + "\n>>> HERA: Turning off mini fan..." + Color.RESET)
				mqtt_system.send_rpc_command("setValueMiniFan", False)

			elif choice == "12":
				print(Color.BLUE + "\n>>> HERA: Setting fan speed..." + Color.RESET)
				try:
					val = int(
						input(
							Color.BLUE
							+ "Enter Fan Speed (0-1023): "
							+ Color.RESET
						).strip()
					)
					mqtt_system.send_rpc_command("setFanSpeed", val)
				except ValueError:
					print(Color.RED + "Invalid input. Please enter a number." + Color.RESET)

			elif choice == "13":
				print(Color.GREEN + "\n>>> HERA: Turning on relay..." + Color.RESET)
				mqtt_system.send_rpc_command("setValueRelay", True)

			elif choice == "14":
				print(Color.YELLOW + "\n>>> HERA: Turning off relay..." + Color.RESET)
				mqtt_system.send_rpc_command("setValueRelay", False)

			elif choice == "15":
				print(Color.CYAN + "\n[ FETCHING SENSOR DATA ]" + Color.RESET)
				if (
					hasattr(mqtt_system, "latest_sensor_data")
					and mqtt_system.latest_sensor_data
				):
					sensors = mqtt_system.latest_sensor_data.get("sensors", {})
					dht20 = sensors.get("dht20", {})
					light_sensor = sensors.get("light", {})
					temp = dht20.get("temperature", "N/A")
					hum = dht20.get("humidity", "N/A")
					light = light_sensor.get("value", "N/A")

					print(f"  - Temperature : {Color.YELLOW}{temp}°C{Color.RESET}")
					print(f"  - Humidity    : {Color.BLUE}{hum}%{Color.RESET}")
					print(f"  - Light       : {Color.YELLOW}{light}{Color.RESET}")
				else:
					print(
						Color.RED
						+ "  - Waiting for the board to send data, please try again in a few seconds..."
						+ Color.RESET
					)

			elif choice == "16":
				print(Color.CYAN + "\n[ FETCHING DEVICE STATUS ]" + Color.RESET)
				if (
					hasattr(mqtt_system, "latest_sensor_data")
					and mqtt_system.latest_sensor_data
				):
					devices = mqtt_system.latest_sensor_data.get("devices", {})

					def format_status(status):
						if str(status).lower() in ["true", "on", "1"]:
							return f"{Color.GREEN}ON{Color.RESET}"
						if str(status).lower() in ["false", "off", "0"]:
							return f"{Color.RED}OFF{Color.RESET}"
						return str(status)

					print(
						f"  - LED       : {format_status(devices.get('led', {}).get('status', 'Unknown'))}"
					)
					print(
						f"  - NeoPixel  : {format_status(devices.get('neo_led', {}).get('status', 'Unknown'))} "
						f"(Brightness: {devices.get('neo_led', {}).get('brightness', 'N/A')})"
					)
					print(
						f"  - WS2812    : {format_status(devices.get('ws2812', {}).get('status', 'Unknown'))} "
						f"(Brightness: {devices.get('ws2812', {}).get('brightness', 'N/A')})"
					)
					print(
						f"  - Relay     : {format_status(devices.get('relay', {}).get('status', 'Unknown'))}"
					)
					print(
						f"  - Mini fan  : {format_status(devices.get('mini_fan', {}).get('status', 'Unknown'))} "
						f"(Speed: {devices.get('mini_fan', {}).get('speed', 'N/A')})"
					)
				else:
					print(Color.RED + "  - Waiting for telemetry..." + Color.RESET)

			elif choice == "17":
				print(Color.CYAN + "\n[ FETCHING NETWORK STATUS ]" + Color.RESET)
				if (
					hasattr(mqtt_system, "latest_sensor_data")
					and mqtt_system.latest_sensor_data
				):
					network = mqtt_system.latest_sensor_data.get("network", {})

					wifi_conn = (
						f"{Color.GREEN}Connected{Color.RESET}"
						if network.get("wifi_connected")
						else f"{Color.RED}Disconnected{Color.RESET}"
					)
					mqtt_conn = (
						f"{Color.GREEN}Connected{Color.RESET}"
						if network.get("mqtt_connected")
						else f"{Color.RED}Disconnected{Color.RESET}"
					)

					print(f"  - WiFi Status  : {wifi_conn}")
					print(
						f"  - WiFi RSSI    : {Color.YELLOW}{network.get('wifi_rssi', 'Unknown')} dBm{Color.RESET}"
					)
					print(
						f"  - WiFi IP      : {Color.BLUE}{network.get('wifi_ip', 'Unknown')}{Color.RESET}"
					)
					print(f"  - MQTT Status  : {mqtt_conn}")
					print(f"  - Uptime       : {network.get('uptime_ms', 'Unknown')} ms")
				else:
					print(Color.RED + "  - Waiting for telemetry..." + Color.RESET)

			elif choice == "18":
				print(Color.CYAN + "\n[ FULL TELEMETRY DATA ]" + Color.RESET)
				if (
					hasattr(mqtt_system, "latest_sensor_data")
					and mqtt_system.latest_sensor_data
				):
					json_str = json.dumps(
						mqtt_system.latest_sensor_data,
						indent=2,
						ensure_ascii=False,
					)
					print(Color.YELLOW + json_str + Color.RESET)
				else:
					print(Color.RED + "  - Waiting for telemetry..." + Color.RESET)

			else:
				print(
					Color.RED
					+ Color.BOLD
					+ "\n[ WARNING ] Invalid choice. Please enter a number from 0 to 18."
					+ Color.RESET
				)

	except KeyboardInterrupt:
		print("Closing connection...")
	finally:
		mqtt_system.client.disconnect()
