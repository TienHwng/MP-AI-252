print("Hello Core IOT !")

import paho.mqtt.client as mqttclient
import time
import json

BROKER_ADDRESS = "app.coreiot.io"
PORT = 1883
ACCESS_TOKEN = "AnynNEWjyN9h0i9yQuvI"

temp = 10
humi = 30
light_intensity = 100

# H6
long = 106.80633605864662
lat = 10.880018410410052

neo_led_state = False


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "on", "yes"):
            return True
        if v in ("false", "0", "off", "no"):
            return False
    return False


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected successfully!!")
        client.subscribe("v1/devices/me/rpc/request/+")
        print("Subscribed to: v1/devices/me/rpc/request/+")
    else:
        print("Connection failed, code:", rc)


def on_subscribe(client, userdata, mid, granted_qos):
    print("Subscribed RPC topic...")


def on_message(client, userdata, message):
    global neo_led_state

    print("\n===== RPC MESSAGE RECEIVED =====")
    print("Topic   :", message.topic)
    payload_str = message.payload.decode("utf-8")
    print("Payload :", payload_str)

    try:
        data = json.loads(payload_str)
    except Exception as e:
        print("JSON parse error:", e)
        return

    method = data.get("method")
    params = data.get("params")

    topic_parts = message.topic.split("/")
    request_id = topic_parts[-1] if len(topic_parts) > 0 else None

    print("Method  :", method)
    print("Params  :", params)
    print("Req ID  :", request_id)

    # RPC: bật/tắt Neo LED
    if method == "setValueNeoLed":
        neo_led_state = parse_bool(params)
        print(f"[RPC] setValueNeoLed -> {neo_led_state}")

        attr_payload = {"neo_led_state": neo_led_state}
        client.publish("v1/devices/me/attributes",
                       json.dumps(attr_payload),
                       qos=1)
        print("Sent attributes:", attr_payload)

        if request_id is not None:
            response_topic = f"v1/devices/me/rpc/response/{request_id}"
            response_payload = {
                "result": "OK",
                "neo_led_state": neo_led_state
            }
            client.publish(response_topic,
                           json.dumps(response_payload),
                           qos=1)
            print("Sent RPC response to:", response_topic)

    elif method == "getDeviceInfo":
        # ví dụ: RPC khác để lấy info thiết bị
        info = {
            "temperature": temp,
            "humidity": humi,
            "light": light_intensity,
            "location": {"lat": lat, "long": long},
            "neo_led_state": neo_led_state
        }
        if request_id is not None:
            response_topic = f"v1/devices/me/rpc/response/{request_id}"
            client.publish(response_topic, json.dumps(info), qos=1)
            print("Sent device info to:", response_topic)
            print("Payload:", info)
    else:
        print("Unknown RPC method:", method)


def main():
    global temp, humi, light_intensity

    client = mqttclient.Client("SENSOR_DHT20_CLIENT")
    # Access token làm username, password rỗng
    client.username_pw_set(username=ACCESS_TOKEN, password="")

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message

    client.connect(BROKER_ADDRESS, PORT, keepalive=60)
    client.loop_start()

    print("Start sending telemetry...")

    try:
        while True:
            telemetry = {
                "temperature": temp,
                "humidity": humi,
                "light": light_intensity,
                "long": long,
                "lat": lat
            }

            client.publish("v1/devices/me/telemetry",
                           json.dumps(telemetry),
                           qos=1)
            print("Telemetry sent:", telemetry)

            temp += 1
            humi += 1
            light_intensity += 1

            time.sleep(5)

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
