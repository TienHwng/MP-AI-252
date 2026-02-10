"""
Omniverse Digital Twin Connector — Dual LED
===========================================
Control LEDs in the Omniverse scene via MQTT,
synchronized with the device simulator + HERA Telegram bot.

Simulated LEDs:
    1. White Indicator LED — 4 prims (SphereLight1, 8, 9, 10) intensity 3000
    2. NeoPixel RGB LED — 1 prim (SphereLight2) intensity 30000

Usage:
    1. Start Mosquitto
    2. Run device_simulator.py
    3. In Omniverse: Window → Script Editor → paste → Run
"""

import json
import atexit
import time
import random

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[OV] paho-mqtt chưa cài! Chạy trong Script Editor:")
    print('    import omni.kit.pipapi; omni.kit.pipapi.install("paho-mqtt")')
    raise

import omni.usd
import omni.kit.app
from pxr import UsdLux, Gf


# ==================== CONFIGURATION ====================

MQTT_BROKER = "localhost"
MQTT_PORT = 1883

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
MAIN_LED_COLOR = Gf.Vec3f(1.0, 1.0, 1.0)   # White
NEO_LED_COLOR = Gf.Vec3f(0.2, 0.8, 1.0)    # Cyan (simulated RGB)


# ==================== STATE ====================

_mqtt_client = None
_update_sub = None
_main_led_on = False
_neo_led_on = False
_needs_update = False
_is_connected = False
_reconnect_timer = 0
_connection_attempts = 0


# ==================== HELPERS ====================

def _get_stage():
    return omni.usd.get_context().get_stage()


def _set_sphere_light(prim_path: str, on: bool, intensity: float, color: Gf.Vec3f):
    """Set intensity and color for a SphereLight prim."""
    stage = _get_stage()
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


def _update_all_main_leds(on: bool):
    """Update all 4 white indicator LEDs at once."""
    for prim_path in MAIN_LED_PATHS:
        _set_sphere_light(prim_path, on, MAIN_LED_INTENSITY, MAIN_LED_COLOR)


def _update_all_neo_leds(on: bool):
    """Update the NeoPixel RGB LED."""
    _set_sphere_light(NEO_LED_PATH, on, NEO_LED_INTENSITY, NEO_LED_COLOR)


# Map MQTT keys → led_type
# Telemetry uses snake_case, RPC responses use PascalCase
_LED_KEY_MAP = {
    "led_state": "main",
    "LedState":  "main",
    "neo_led_state": "neo",
    "NeoLedState":   "neo",
}


# ==================== MQTT CALLBACKS ====================

def on_connect(client, userdata, flags, rc, properties=None):
    global _is_connected, _connection_attempts
    if rc == 0:
        _is_connected = True
        _connection_attempts = 0
        client.subscribe("v1/devices/me/telemetry")
        client.subscribe("v1/devices/me/attributes")
        print("[OV] ✅ MQTT connected")
    else:
        _is_connected = False
        _connection_attempts += 1
        print(f"[OV] ❌ Connection failed rc={rc}")


def on_disconnect(client, userdata, flags, rc, properties=None):
    global _is_connected, _connection_attempts
    _is_connected = False
    if rc != 0:
        _connection_attempts += 1
        if _connection_attempts <= 3:
            print(f"[OV] 🔌 Disconnected (attempt {_connection_attempts})")
    else:
        print("[OV] 🔌 Disconnected (clean)")


def on_message(client, userdata, msg):
    """Update LED state from telemetry / attributes."""
    global _main_led_on, _neo_led_on, _needs_update
    try:
        data = json.loads(msg.payload.decode())
        for key, led_type in _LED_KEY_MAP.items():
            if key not in data:
                continue
            new_state = bool(data[key])
            if led_type == "main" and new_state != _main_led_on:
                _main_led_on = new_state
                _needs_update = True
                print(f"[OV] Main LED → {'ON' if new_state else 'OFF'}")
            elif led_type == "neo" and new_state != _neo_led_on:
                _neo_led_on = new_state
                _needs_update = True
                print(f"[OV] Neo LED → {'ON' if new_state else 'OFF'}")
    except Exception as e:
        print(f"[OV] Parse error: {e}")


# ==================== UPDATE LOOP ====================

def on_update(e):
    """Per-frame callback — apply LED changes on Omniverse main thread."""
    global _needs_update, _reconnect_timer

    if _needs_update:
        _needs_update = False
        _update_all_main_leds(_main_led_on)
        _update_all_neo_leds(_neo_led_on)

    # Auto-reconnect với exponential backoff
    if _mqtt_client and not _is_connected:
        _reconnect_timer += 1
        # Backoff: 5s, 10s, 15s (tối đa) — đơn vị frame ≈ 60fps
        delay = min(_connection_attempts * 300, 900)
        if _reconnect_timer >= delay:
            _reconnect_timer = 0
            if _connection_attempts <= 10:
                try:
                    if _connection_attempts == 1:
                        print("[OV] 🔄 Attempting reconnect...")
                    _mqtt_client.reconnect()
                except Exception as e:
                    if _connection_attempts <= 3:
                        print(f"[OV] ⚠️ Reconnect failed: {e}")


# ==================== START / STOP ====================

def start():
    global _mqtt_client, _update_sub, _is_connected
    global _reconnect_timer, _connection_attempts

    if _mqtt_client:
        stop()

    print("=" * 50)
    print("  🚀 Digital Twin — Dual LED (Auto-reconnect)")
    print("=" * 50)
    print(f"  White LED (4x): {', '.join(MAIN_LED_PATHS)} [intensity {MAIN_LED_INTENSITY}]")
    print(f"  Neo LED (1x)  : {NEO_LED_PATH} [intensity {NEO_LED_INTENSITY}]")
    print(f"  Broker        : {MQTT_BROKER}:{MQTT_PORT}\n")

    _is_connected = False
    _reconnect_timer = 0
    _connection_attempts = 0

    # Unique client ID — avoid conflicts with broker
    ts = int(time.time() * 1000) % 100000
    rid = random.randint(1000, 9999)
    _mqtt_client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, f"OV_{ts}_{rid}"
    )
    _mqtt_client.on_connect = on_connect
    _mqtt_client.on_message = on_message
    _mqtt_client.on_disconnect = on_disconnect
    _mqtt_client.reconnect_delay_set(min_delay=2, max_delay=30)

    try:
        _mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
        _mqtt_client.loop_start()
    except Exception as e:
        print(f"[OV] ❌ Không kết nối được: {e}")
        return

    if not _update_sub:
        app = omni.kit.app.get_app()
        _update_sub = (
            app.get_update_event_stream().create_subscription_to_pop(on_update)
        )

    print("[OV] 🎯 Ready! Use the HERA bot to control.")
    print("[OV] 🔄 Auto-reconnect enabled.\n")


def stop():
    global _mqtt_client, _update_sub, _is_connected

    if _update_sub:
        _update_sub.unsubscribe()
        _update_sub = None

    if _mqtt_client:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
        except Exception:
            pass
        finally:
            _mqtt_client = None

    _is_connected = False
    print("[OV] ✅ Stopped.")


def restart():
    """Restart the connector — useful for debugging."""
    print("[OV] 🔄 Restarting...")
    stop()
    start()


def _cleanup_on_exit():
    """Cleanup when Omniverse exits."""
    if _mqtt_client:
        stop()


# ==================== AUTO-START ====================

atexit.register(_cleanup_on_exit)
print("[OV] 🎬 Starting Digital Twin connector...")
print("[OV] 💡 Use restart() to reconnect if needed.")
start()
