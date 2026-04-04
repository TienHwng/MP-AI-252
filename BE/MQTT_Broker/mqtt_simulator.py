import json
import time
import random
import threading

import paho.mqtt.client as mqtt


# =========================
# CONFIG
# =========================
MQTT_SERVER = "192.168.1.2"
MQTT_PORT = 1883
COREIOT_TOKEN = "ehehehe"

TOPIC_TELEMETRY = "v1/devices/me/telemetry"
TOPIC_RPC_REQUEST = "v1/devices/me/rpc/request/+"
TOPIC_RPC_RESPONSE_PREFIX = "v1/devices/me/rpc/response/"
TOPIC_ATTRIBUTES = "v1/devices/me/attributes"

CLIENT_ID = "ESP32_AIoT_Core_Python_Simulator"
TELEMETRY_INTERVAL = 5  # seconds


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
    "relay_status": False,
    "mini_fan_status": False,
}

sensor_state = {
    "temperature": 30.0,
    "humidity": 60.0,
    "light": 90.0,
}

network_state = {
    "wifi_connected": True,
    "wifi_rssi": -55,
    "wifi_ip": "192.168.1.50",
    "mqtt_connected": False,
}


# =========================
# HELPERS
# =========================
def uptime_ms() -> int:
    return int((time.time() - start_time) * 1000)


def pretty_json(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def update_fake_sensor_data():
    with state_lock:
        sensor_state["temperature"] = round(random.uniform(25.0, 35.0), 2)
        sensor_state["humidity"] = round(random.uniform(45.0, 80.0), 2)
        sensor_state["light"] = round(random.uniform(10.0, 100.0), 2)
        network_state["wifi_rssi"] = random.randint(-75, -40)


# =========================
# MQTT CALLBACKS
# =========================
def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties=None):
    with state_lock:
        network_state["mqtt_connected"] = (reason_code == 0)

    if reason_code == 0:
        print("[MQTT] Connected successfully")
        client.subscribe(TOPIC_RPC_REQUEST)
        print(f"[MQTT] Subscribed: {TOPIC_RPC_REQUEST}")
    else:
        print(f"[MQTT] Connect failed, reason_code={reason_code}")


def on_disconnect(client: mqtt.Client, userdata, disconnect_flags, reason_code, properties=None):
    with state_lock:
        network_state["mqtt_connected"] = False
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

    if not isinstance(params, bool):
        print("[MQTT] params is not bool!")
        return

    request_id = topic.split("/")[-1]
    response = {}

    with state_lock:
        if method == "setValueLedBlinky":
            device_state["led_status"] = params
            print("💡 Turning on normal LED" if params else "💡 Turning off normal LED")
            response["LedState"] = params

        elif method == "setValueNeoLed":
            device_state["neo_led_status"] = params
            print("🌈 Turning on NeoPixel" if params else "🌈 Turning off NeoPixel")
            response["NeoLedState"] = params

        elif method == "setValueWS2812":
            device_state["ws2812_status"] = params
            print("🎇 Turning on WS2812" if params else "🎇 Turning off WS2812")
            response["WS2812State"] = params

        elif method == "setValueRelay":
            device_state["relay_status"] = params
            print("🔌 Turning on Relay" if params else "🔌 Turning off Relay")
            response["RelayState"] = params

        elif method == "setValueMiniFan":
            device_state["mini_fan_status"] = params
            print("🌀 Turning on Fan" if params else "🌀 Turning off Fan")
            response["FanState"] = params

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
                "led_status": device_state["led_status"],
                "neo_led_status": device_state["neo_led_status"],
                "ws2812_status": device_state["ws2812_status"],
                "relay_status": device_state["relay_status"],
                "mini_fan_status": device_state["mini_fan_status"],
            },
            "sensors": {
                "temperature": sensor_state["temperature"],
                "humidity": sensor_state["humidity"],
                "light": sensor_state["light"],
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
        else:
            print(f"[MQTT] Publish failed, rc={result.rc}")

        time.sleep(TELEMETRY_INTERVAL)


# =========================
# MAIN
# =========================
def build_client() -> mqtt.Client:
    client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311)
    client.username_pw_set(COREIOT_TOKEN)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    return client


def main():
    global running

    client = build_client()

    print(f"[MQTT] Connecting to broker {MQTT_SERVER}:{MQTT_PORT} ...")
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