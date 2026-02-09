"""
ESP32 IoT Device Simulator
===========================
Simulates the ESP32 DHT20 sensor + LED/NeoPixel device over MQTT.
Publishes fake telemetry and responds to RPC commands (LED on/off, NeoLED on/off).

Usage:
    python device_simulator.py

Requires: A running MQTT broker on localhost:1883 (Mosquitto).
"""

import paho.mqtt.client as mqtt
import json
import time
import random
import threading

# ============== CONFIGURATION ==============
MQTT_BROKER = "localhost"
MQTT_PORT   = 1883

# MQTT Topics (matches the real ESP32 firmware / ThingsBoard format)
TOPIC_TELEMETRY     = "v1/devices/me/telemetry"
TOPIC_RPC_REQUEST   = "v1/devices/me/rpc/request/+"
TOPIC_RPC_RESPONSE  = "v1/devices/me/rpc/response/"
TOPIC_ATTRIBUTES    = "v1/devices/me/attributes"

# How often to publish sensor data (seconds)
TELEMETRY_INTERVAL  = 5
# ============================================


# ---------- Simulated Device State ----------
device_state = {
    "temperature": 28.5,
    "humidity": 65.0,
    "inference_result": 0.12,
    "led": True,
    "neo_led": True,
}

# Normal ranges (same as the real TinyML model)
TEMP_NORMAL_MIN = 25.0
TEMP_NORMAL_MAX = 35.0
HUMI_NORMAL_MIN = 60.0
HUMI_NORMAL_MAX = 80.0


def simulate_anomaly_score(temp: float, humi: float) -> float:
    """Mimic the TinyML anomaly model output (0..1). >0.5 = anomaly."""
    is_anomalous = (
        temp < TEMP_NORMAL_MIN or temp > TEMP_NORMAL_MAX or
        humi < HUMI_NORMAL_MIN or humi > HUMI_NORMAL_MAX
    )
    if is_anomalous:
        return round(random.uniform(0.60, 0.95), 4)
    else:
        return round(random.uniform(0.05, 0.30), 4)


# ---------- MQTT Callbacks ----------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[Simulator] Connected to MQTT broker!")
        client.subscribe(TOPIC_RPC_REQUEST)
        print(f"[Simulator] Subscribed to: {TOPIC_RPC_REQUEST}")
    else:
        print(f"[Simulator] Connection failed with code {rc}")


def on_message(client, userdata, msg):
    """Handle incoming RPC commands from the HERA bot."""
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print(f"[Simulator] Invalid JSON on {msg.topic}")
        return

    method = payload.get("method", "")
    params = payload.get("params")
    request_id = msg.topic.split("/")[-1]

    print(f"\n[Simulator] ⚡ RPC received: method={method}, params={params}")

    if method == "setValueLedBlinky":
        device_state["led"] = bool(params)
        status = "ON" if device_state["led"] else "OFF"
        print(f"[Simulator] 💡 LED is now {status}")

        feedback = json.dumps({"LedState": device_state["led"]})
        client.publish(f"{TOPIC_RPC_RESPONSE}{request_id}", feedback)
        client.publish(TOPIC_ATTRIBUTES, feedback)

    elif method == "setValueNeoLed":
        device_state["neo_led"] = bool(params)
        status = "ON" if device_state["neo_led"] else "OFF"
        print(f"[Simulator] 🌈 NeoPixel LED is now {status}")

        feedback = json.dumps({"NeoLedState": device_state["neo_led"]})
        client.publish(f"{TOPIC_RPC_RESPONSE}{request_id}", feedback)
        client.publish(TOPIC_ATTRIBUTES, feedback)

    else:
        print(f"[Simulator] ⚠️  Unknown method: {method}")


# ---------- Telemetry Publisher ----------
def publish_telemetry(client):
    """Publish simulated sensor data every TELEMETRY_INTERVAL seconds."""
    print(f"\n[Simulator] Publishing telemetry every {TELEMETRY_INTERVAL}s...\n")

    while True:
        # Random-walk the sensor values (slow drift, like a real sensor)
        device_state["temperature"] += random.uniform(-0.3, 0.3)
        device_state["humidity"]    += random.uniform(-0.8, 0.8)

        # Clamp to physically reasonable ranges
        device_state["temperature"] = round(max(15.0, min(45.0, device_state["temperature"])), 2)
        device_state["humidity"]    = round(max(30.0, min(95.0, device_state["humidity"])),    2)

        # Compute simulated anomaly score
        device_state["inference_result"] = simulate_anomaly_score(
            device_state["temperature"],
            device_state["humidity"]
        )

        payload = {
            "temperature":      device_state["temperature"],
            "humidity":         device_state["humidity"],
            "inference_result": device_state["inference_result"],
            "led_state":        device_state["led"],
            "neo_led_state":    device_state["neo_led"],
        }

        client.publish(TOPIC_TELEMETRY, json.dumps(payload))

        print(
            f"[Simulator] 📡 T={payload['temperature']}°C  "
            f"H={payload['humidity']}%  "
            f"Anomaly={payload['inference_result']}  "
            f"LED={'ON' if payload['led_state'] else 'OFF'}  "
            f"NeoLED={'ON' if payload['neo_led_state'] else 'OFF'}"
        )

        time.sleep(TELEMETRY_INTERVAL)


# ---------- Main ----------
def main():
    print("=" * 55)
    print("   ESP32 IoT Device Simulator")
    print("=" * 55)
    print(f"Broker : {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Interval: every {TELEMETRY_INTERVAL}s\n")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "ESP32_Simulator")
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
    except ConnectionRefusedError:
        print("❌ Cannot connect to MQTT broker!")
        print("   Make sure Mosquitto is running on localhost:1883")
        print("   Install: winget install EclipseFoundation.Mosquitto")
        print("   Start:   net start mosquitto")
        return

    # Start telemetry in a background thread
    telemetry_thread = threading.Thread(target=publish_telemetry, args=(client,), daemon=True)
    telemetry_thread.start()

    # Block on the MQTT network loop (also handles incoming RPC)
    print("[Simulator] Running... Press Ctrl+C to stop.\n")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[Simulator] Stopped.")
        client.disconnect()


if __name__ == "__main__":
    main()
