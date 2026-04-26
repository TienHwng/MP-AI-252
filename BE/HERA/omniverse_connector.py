"""
Omniverse Digital Twin Connector — Dual LED
===========================================
Control LEDs in the Omniverse scene via MQTT,
synchronized with the real ESP32 hardware + HERA Telegram bot.

Simulated LEDs:
    1. White Indicator LED — 4 prims (SphereLight1, 8, 9, 10) intensity 3000
    2. NeoPixel RGB LED — 1 prim (SphereLight2) intensity 30000

Usage:
    1. Start HERA (which starts the MQTT broker)
    2. Connect ESP32 hardware
    3. In Omniverse: Window → Script Editor → paste → Run
"""

import atexit
import json
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv

try:
	import paho.mqtt.client as mqtt
except ImportError:
	print("[OV] paho-mqtt chưa cài! Chạy trong Script Editor:")
	print('    import omni.kit.pipapi; omni.kit.pipapi.install("paho-mqtt")')
	raise

import omni.kit.app
import omni.usd
from pxr import Gf, UsdLux

# ==================== CONFIGURATION ====================


ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV_PATH)

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT"))

# White LED (MAIN LED) — control 4 prims at once
MAIN_LED_PATHS = [
	"/SphereLight1",
	"/SphereLight8",
	"/SphereLight9",
	"/SphereLight10",
]

# NeoPixel RGB (NEO LED) — single prim
NEO_LED_PATH = "/SphereLight2"

# Intensity values
MAIN_LED_INTENSITY = 3000.0
NEO_LED_INTENSITY = 30000.0
LED_OFF_INTENSITY = 0.0

# Colors
MAIN_LED_COLOR = Gf.Vec3f(1.0, 1.0, 1.0)  # White
NEO_LED_COLOR = Gf.Vec3f(0.2, 0.8, 1.0)  # Cyan (simulated RGB)


# ==================== STATE ====================


mqtt_client = None
update_sub = None
main_led_on = False
neo_led_on = False
needs_update = False
is_connected = False
reconnect_timer = 0
connection_attempts = 0


# ==================== HELPERS ====================


def get_stage():
	return omni.usd.get_context().get_stage()


def set_sphere_light(prim_path: str, on: bool, intensity: float, color: Gf.Vec3f):
	"""Set intensity and color for a SphereLight prim."""
	stage = get_stage()
	if not stage:
		return
	prim = stage.GetPrimAtPath(prim_path)
	if not prim.IsValid():
		return  # Silent fail if the prim does not exist
	light = UsdLux.SphereLight(prim)
	if not light:
		return
	light.GetIntensityAttr().Set(intensity if on else LED_OFF_INTENSITY)
	if on:
		light.GetColorAttr().Set(color)


def update_all_main_leds(on: bool):
	"""Update all 4 white indicator LEDs at once."""
	for prim_path in MAIN_LED_PATHS:
		set_sphere_light(prim_path, on, MAIN_LED_INTENSITY, MAIN_LED_COLOR)


def update_all_neo_leds(on: bool):
	"""Update the NeoPixel RGB LED."""
	set_sphere_light(NEO_LED_PATH, on, NEO_LED_INTENSITY, NEO_LED_COLOR)


# Map MQTT keys → led_type
# Telemetry uses snake_case, RPC responses use PascalCase
LED_KEY_MAP = {
	"led_state": "main",
	"LedState": "main",
	"neo_led_state": "neo",
	"NeoLedState": "neo",
}


# ==================== MQTT CALLBACKS ====================


def on_connect(client, userdata, flags, rc, properties=None):
	global is_connected, connection_attempts
	if rc == 0:
		is_connected = True
		connection_attempts = 0
		client.subscribe("v1/devices/me/telemetry")
		client.subscribe("v1/devices/me/attributes")
		print("[OV] [ OK ] MQTT connected")
	else:
		is_connected = False
		connection_attempts += 1
		print(f"[OV] [ ERROR ] Connection failed rc={rc}")


def on_disconnect(client, userdata, flags, rc, properties=None):
	global is_connected, connection_attempts
	is_connected = False
	if rc != 0:
		connection_attempts += 1
		if connection_attempts <= 3:
			print(f"[OV] [ INFO ] Disconnected (attempt {connection_attempts})")
	else:
		print("[OV] [ INFO ] Disconnected (clean)")


def on_message(client, userdata, msg):
	"""Update LED state from telemetry / attributes."""
	global main_led_on, neo_led_on, needs_update
	try:
		data = json.loads(msg.payload.decode())

		devices = data.get("devices") if isinstance(data.get("devices"), dict) else {}
		main_device = devices.get("led") if isinstance(devices.get("led"), dict) else {}
		neo_device = (
			devices.get("neo_led") if isinstance(devices.get("neo_led"), dict) else {}
		)
		main_state = main_device.get("status")
		neo_state = neo_device.get("status")

		if main_state is not None:
			new_state = bool(main_state)
			if new_state != main_led_on:
				main_led_on = new_state
				needs_update = True
				print(f"[OV] Main LED → {'ON' if new_state else 'OFF'}")

		if neo_state is not None:
			new_state = bool(neo_state)
			if new_state != neo_led_on:
				neo_led_on = new_state
				needs_update = True
				print(f"[OV] Neo LED → {'ON' if new_state else 'OFF'}")
	except Exception as e:
		print(f"[OV] Parse error: {e}")


# ==================== UPDATE LOOP ====================


def on_update(e):
	"""Per-frame callback — apply LED changes on Omniverse main thread."""
	global needs_update, reconnect_timer

	if needs_update:
		needs_update = False
		update_all_main_leds(main_led_on)
		update_all_neo_leds(neo_led_on)

	# Auto-reconnect với exponential backoff
	if mqtt_client and not is_connected:
		reconnect_timer += 1
		# Backoff: 5s, 10s, 15s (tối đa) — đơn vị frame ≈ 60fps
		delay = min(connection_attempts * 300, 900)
		if reconnect_timer >= delay:
			reconnect_timer = 0
			if connection_attempts <= 10:
				try:
					if connection_attempts == 1:
						print("[OV] [ INFO ] Attempting reconnect...")
					mqtt_client.reconnect()
				except Exception as e:
					if connection_attempts <= 3:
						print(f"[OV] [ WARNING ] Reconnect failed: {e}")


# ==================== START / STOP ====================


def start():
	global mqtt_client, update_sub, is_connected
	global reconnect_timer, connection_attempts

	if mqtt_client:
		stop()

	print("=" * 50)
	print("  [ INFO ] Digital Twin — Dual LED (Auto-reconnect)")
	print("=" * 50)
	print(
		f"  White LED (4x): {', '.join(MAIN_LED_PATHS)} [intensity {MAIN_LED_INTENSITY}]"
	)
	print(f"  Neo LED (1x)  : {NEO_LED_PATH} [intensity {NEO_LED_INTENSITY}]")
	print(f"  Broker        : {MQTT_BROKER}:{MQTT_PORT}\n")

	is_connected = False
	reconnect_timer = 0
	connection_attempts = 0

	# Unique client ID — avoid conflicts with broker
	ts = int(time.time() * 1000) % 100000
	rid = random.randint(1000, 9999)
	mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, f"OV_{ts}_{rid}")
	mqtt_client.on_connect = on_connect
	mqtt_client.on_message = on_message
	mqtt_client.on_disconnect = on_disconnect
	mqtt_client.reconnect_delay_set(min_delay=2, max_delay=30)

	try:
		mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
		mqtt_client.loop_start()
	except Exception as e:
		print(f"[OV] [ ERROR ] Không kết nối được: {e}")
		return

	if not update_sub:
		app = omni.kit.app.get_app()
		update_sub = app.get_update_event_stream().create_subscription_to_pop(on_update)

	print("[OV] [ INFO ] Ready! Use the HERA bot to control.")
	print("[OV] [ INFO ] Auto-reconnect enabled.\n")


def stop():
	global mqtt_client, update_sub, is_connected

	if update_sub:
		update_sub.unsubscribe()
		update_sub = None

	if mqtt_client:
		try:
			mqtt_client.loop_stop()
			mqtt_client.disconnect()
		except Exception:
			pass
		finally:
			mqtt_client = None

	is_connected = False
	print("[OV] [ OK ] Stopped.")


def restart():
	"""Restart the connector — useful for debugging."""
	print("[OV] [ INFO ] Restarting...")
	stop()
	start()


def cleanup_on_exit():
	"""Cleanup when Omniverse exits."""
	if mqtt_client:
		stop()


# ==================== AUTO-START ====================


atexit.register(cleanup_on_exit)
print("[OV] [ INFO ] Starting Digital Twin connector...")
print("[OV] [ INFO ] Use restart() to reconnect if needed.")
start()
