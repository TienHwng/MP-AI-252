"""
Omniverse Digital Twin Connector — LED Demo
=============================================
Controls ONE SphereLight in your scene via MQTT,
matching the device simulator + HERA Telegram bot.

How to run:
  1. Start Mosquitto on your laptop
  2. Start device_simulator.py in a terminal
  3. In Omniverse: Window → Script Editor → paste this → Run
"""

import json
try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[OV] paho-mqtt not found! Run this in Script Editor first:")
    print('    import omni.kit.pipapi; omni.kit.pipapi.install("paho-mqtt")')
    raise

import omni.usd
import omni.kit.app
from pxr import UsdLux, Gf


# CONFIGURATION
MQTT_BROKER = "localhost"
MQTT_PORT   = 1883

# Your SphereLight prim path — the one you just tested manually
LED_LIGHT_PATH = "/SphereLight"

# Intensity values — same ones you tested: 0 = off, 30000 = on
LED_ON_INTENSITY  = 30000.0
LED_OFF_INTENSITY = 0.0

# Color when LED is on — warm yellow
LED_ON_COLOR = Gf.Vec3f(1.0, 0.85, 0.4)


# STATE
_mqtt_client  = None
_update_sub   = None
_led_on       = False
_needs_update = False


# HELPERS
def get_stage():
    return omni.usd.get_context().get_stage()


def set_sphere_light(on: bool):
    """Set the SphereLight intensity and color."""
    stage = get_stage()
    if not stage:
        return

    prim = stage.GetPrimAtPath(LED_LIGHT_PATH)
    if not prim.IsValid():
        print(f"[OV] Prim not found: {LED_LIGHT_PATH}")
        return

    light = UsdLux.SphereLight(prim)
    if not light:
        print(f"[OV] Not a SphereLight: {LED_LIGHT_PATH}")
        return

    if on:
        light.GetIntensityAttr().Set(LED_ON_INTENSITY)
        light.GetColorAttr().Set(LED_ON_COLOR)
    else:
        light.GetIntensityAttr().Set(LED_OFF_INTENSITY)


# MQTT CALLBACKS
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[OV] Connected to MQTT broker")
        client.subscribe("v1/devices/me/telemetry")
        client.subscribe("v1/devices/me/attributes")
    else:
        print(f"[OV] MQTT failed rc={rc}")


def on_message(client, userdata, msg):
    global _led_on, _needs_update
    try:
        data = json.loads(msg.payload.decode())

        if "led_state" in data:
            new_state = bool(data["led_state"])
            if new_state != _led_on:
                _led_on = new_state
                _needs_update = True
                print(f"[OV] LED -> {'ON' if _led_on else 'OFF'}")

        if "LedState" in data:
            new_state = bool(data["LedState"])
            if new_state != _led_on:
                _led_on = new_state
                _needs_update = True
                print(f"[OV] LED -> {'ON' if _led_on else 'OFF'}")

    except Exception as e:
        print(f"[OV] Parse error: {e}")


# PER-FRAME UPDATE — safely applies changes on Omniverse's main thread
def on_update(e):
    global _needs_update
    if _needs_update:
        _needs_update = False
        set_sphere_light(_led_on)


# START / STOP
def start():
    global _mqtt_client, _update_sub

    print("=" * 45)
    print("  Digital Twin — LED Demo")
    print("=" * 45)
    print(f"  Light prim : {LED_LIGHT_PATH}")
    print(f"  Broker     : {MQTT_BROKER}:{MQTT_PORT}")
    print()

    _mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "OV_Connector")
    _mqtt_client.on_connect = on_connect
    _mqtt_client.on_message = on_message

    try:
        _mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
        _mqtt_client.loop_start()
    except Exception as e:
        print(f"[OV] Cannot connect to broker: {e}")
        print("  -> Make sure Mosquitto is running!")
        return

    app = omni.kit.app.get_app()
    _update_sub = app.get_update_event_stream().create_subscription_to_pop(on_update)

    print("[OV] Listening... Start device_simulator.py to see it work!")
    print("[OV] Or use HERA bot: 'turn on the LED'")
    print()


def stop():
    global _mqtt_client, _update_sub
    _update_sub = None
    if _mqtt_client:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()
        _mqtt_client = None
    print("[OV] Stopped.")


# Auto-start
start()
