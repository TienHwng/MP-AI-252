"""
Omniverse Digital Twin Connector — Dual LED Demo
=============================================
Controls TWO SphereLight prims in your scene via MQTT,
matching the device simulator + HERA Telegram bot.

LEDs visualized:
1. White Indicator LED (main LED)
2. NeoPixel RGB LED (colorful LED)

How to run:
  1. Start Mosquitto on your laptop
  2. Start device_simulator.py in a terminal
  3. In Omniverse: Window → Script Editor → paste this → Run
"""

import json
import atexit
import time
import random
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

# Your existing SphereLight prim paths from your Chinese interior scene
MAIN_LED_PATH = "/SphereLight1"      # Ceiling lamp - White indicator LED
NEO_LED_PATH  = "/SphereLight2"       # Floor lamp - RGB colorful LED

# Intensity values
LED_ON_INTENSITY  = 30000.0
LED_OFF_INTENSITY = 0.0

# Colors for different LEDs
MAIN_LED_COLOR = Gf.Vec3f(1.0, 1.0, 1.0)    # White (ceiling lamp)
NEO_LED_COLOR  = Gf.Vec3f(0.2, 0.8, 1.0)     # Cyan/Blue for RGB effect (floor lamp)


# STATE
_mqtt_client     = None
_update_sub      = None
_main_led_on     = False
_neo_led_on      = False
_needs_update    = False
_is_connected    = False
_reconnect_timer = 0
_connection_attempts = 0


# HELPERS
def get_stage():
    return omni.usd.get_context().get_stage()


def set_sphere_light(prim_path: str, on: bool, color: Gf.Vec3f):
    """Set a SphereLight intensity and color."""
    stage = get_stage()
    if not stage:
        return

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        print(f"[OV] Prim not found: {prim_path}")
        return

    light = UsdLux.SphereLight(prim)
    if not light:
        print(f"[OV] Not a SphereLight: {prim_path}")
        return

    if on:
        light.GetIntensityAttr().Set(LED_ON_INTENSITY)
        light.GetColorAttr().Set(color)
    else:
        light.GetIntensityAttr().Set(LED_OFF_INTENSITY)


def update_main_led(on: bool):
    """Update the main white LED."""
    set_sphere_light(MAIN_LED_PATH, on, MAIN_LED_COLOR)
    

def update_neo_led(on: bool):
    """Update the NeoPixel RGB LED."""
    set_sphere_light(NEO_LED_PATH, on, NEO_LED_COLOR)


# MQTT CALLBACKS
def on_connect(client, userdata, flags, rc, properties=None):
    global _is_connected, _connection_attempts
    if rc == 0:
        print("[OV] ✅ Connected to MQTT broker")
        _is_connected = True
        _connection_attempts = 0  # Reset counter on successful connection
        client.subscribe("v1/devices/me/telemetry")
        client.subscribe("v1/devices/me/attributes")
        print("[OV] 📡 Subscribed to telemetry channels")
    else:
        print(f"[OV] ❌ MQTT connection failed rc={rc}")
        _is_connected = False
        _connection_attempts += 1


def on_disconnect(client, userdata, flags, rc, properties=None):
    global _is_connected, _connection_attempts  
    _is_connected = False
    if rc != 0:
        _connection_attempts += 1
        if _connection_attempts <= 3:  # Only log first few attempts
            print(f"[OV] 🔌 Connection lost (attempt {_connection_attempts})")
    else:
        print("[OV] 🔌 Cleanly disconnected")


def on_message(client, userdata, msg):
    global _main_led_on, _neo_led_on, _needs_update
    try:
        data = json.loads(msg.payload.decode())
        
        # Handle main LED (white indicator)
        if "led_state" in data:
            new_state = bool(data["led_state"])
            if new_state != _main_led_on:
                _main_led_on = new_state
                _needs_update = True
                print(f"[OV] Main LED (Ceiling) -> {'ON' if _main_led_on else 'OFF'}")

        if "LedState" in data:
            new_state = bool(data["LedState"])
            if new_state != _main_led_on:
                _main_led_on = new_state
                _needs_update = True
                print(f"[OV] Main LED (Ceiling) -> {'ON' if _main_led_on else 'OFF'}")
                
        # Handle Neo LED (RGB colorful)
        if "neo_led_state" in data:
            new_state = bool(data["neo_led_state"])
            if new_state != _neo_led_on:
                _neo_led_on = new_state
                _needs_update = True
                print(f"[OV] Neo LED (Floor) -> {'ON' if _neo_led_on else 'OFF'}")
                
        if "NeoLedState" in data:
            new_state = bool(data["NeoLedState"])
            if new_state != _neo_led_on:
                _neo_led_on = new_state
                _needs_update = True
                print(f"[OV] Neo LED (Floor) -> {'ON' if _neo_led_on else 'OFF'}")

    except Exception as e:
        print(f"[OV] Parse error: {e}")


# PER-FRAME UPDATE — safely applies changes on Omniverse's main thread
def on_update(e):
    global _needs_update, _mqtt_client, _is_connected, _reconnect_timer
    
    # Apply LED updates
    if _needs_update:
        _needs_update = False
        update_main_led(_main_led_on)
        update_neo_led(_neo_led_on)
    
    # Auto-reconnect logic with exponential backoff
    if _mqtt_client and not _is_connected:
        _reconnect_timer += 1
        # Exponential backoff: 5s, 10s, 15s, then 15s intervals
        reconnect_delay = min(_connection_attempts * 300, 900)  # Max 15s (900 frames at 60fps)
        
        if _reconnect_timer >= reconnect_delay:
            _reconnect_timer = 0
            if _connection_attempts <= 10:  # Limit reconnection attempts
                try:
                    if _connection_attempts == 1:
                        print("[OV] 🔄 Attempting reconnection...")
                    _mqtt_client.reconnect()
                except Exception as e:
                    if _connection_attempts <= 3:  # Only log first few failures
                        print(f"[OV] ⚠️  Reconnect failed: {e}")


# START / STOP
def start():
    global _mqtt_client, _update_sub, _is_connected, _reconnect_timer, _connection_attempts
    
    # Clean up any existing connections first
    if _mqtt_client:
        stop()
    
    print("=" * 50)
    print("  🚀 Digital Twin — Dual LED Demo (Forever Edition)")
    print("=" * 50)
    print(f"  Ceiling LED  : {MAIN_LED_PATH} (white indicator)")
    print(f"  Floor LED    : {NEO_LED_PATH} (colorful RGB)")
    print(f"  Broker       : {MQTT_BROKER}:{MQTT_PORT}")
    print()

    # Reset state
    _is_connected = False
    _reconnect_timer = 0
    _connection_attempts = 0
    
    # Create unique client ID with timestamp and random component 
    timestamp = int(time.time() * 1000) % 100000  # Last 5 digits of timestamp
    random_id = random.randint(1000, 9999)
    client_id = f"OV_Connector_{timestamp}_{random_id}"
    
    _mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)
    _mqtt_client.on_connect = on_connect
    _mqtt_client.on_message = on_message
    _mqtt_client.on_disconnect = on_disconnect
    
    # Configure for stability
    _mqtt_client.reconnect_delay_set(min_delay=2, max_delay=30)
    _mqtt_client.max_inflight_messages_set(10)
    _mqtt_client.max_queued_messages_set(100)

    try:
        _mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
        _mqtt_client.loop_start()
        print("[OV] 🔄 MQTT client started with auto-reconnect")
    except Exception as e:
        print(f"[OV] ❌ Cannot connect to broker: {e}")
        print("  -> Make sure Mosquitto is running!")
        return

    # Subscribe to update events (only once)
    if not _update_sub:
        app = omni.kit.app.get_app()
        _update_sub = app.get_update_event_stream().create_subscription_to_pop(on_update)
        print("[OV] 📺 Update subscription created")

    print("[OV] 🎯 Ready! Use HERA bot commands:")
    print("    • 'turn on the white LED' → Ceiling lamp only")
    print("    • 'turn on the colorful LED' → Floor lamp only") 
    print("    • 'turn on all lights' → Both lamps")
    print("    • 'turn off all lights' → Both lamps off")
    print("[OV] 🔄 Auto-reconnect enabled - will work forever!")
    print()


def stop():
    global _mqtt_client, _update_sub, _is_connected
    
    print("[OV] 🛑 Stopping connections...")
    
    if _update_sub:
        _update_sub.unsubscribe()
        _update_sub = None
        print("[OV] 📺 Update subscription removed")
    
    if _mqtt_client:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
            print("[OV] 🔌 MQTT client disconnected")
        except Exception as e:
            print(f"[OV] ⚠️  Error during disconnect: {e}")
        finally:
            _mqtt_client = None
    
    _is_connected = False
    print("[OV] ✅ Stopped cleanly.")


def cleanup_on_exit():
    """Ensures clean shutdown when Omniverse closes"""
    if _mqtt_client:
        print("[OV] 🧹 Omniverse closing - cleaning up MQTT connection...")
        stop()


def restart():
    """Restart the connector - useful for debugging"""
    print("[OV] 🔄 Restarting...")
    stop()
    start()


# Auto-start
print("[OV] 🎬 Auto-starting Digital Twin connector...")
print("[OV] 💡 TIP: Use restart() if you need to reconnect!")

# Register cleanup handler for when Omniverse closes
atexit.register(cleanup_on_exit)

start()
