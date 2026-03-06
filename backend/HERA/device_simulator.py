"""
ESP32 IoT Device Simulator
===========================
Giả lập thiết bị ESP32 (cảm biến DHT20 + LED/NeoPixel) qua MQTT.
Publish telemetry giả và xử lý lệnh RPC (bật/tắt LED).

Cách dùng:
    python device_simulator.py

Yêu cầu: MQTT broker chạy trên localhost:1883 (Mosquitto).
"""

import json
import time
import random
import threading

import paho.mqtt.client as mqtt


# ==================== CẤU HÌNH ====================

MQTT_BROKER = "localhost"
MQTT_PORT = 1883

# MQTT topics — khớp với firmware ESP32 / ThingsBoard
TOPIC_TELEMETRY = "v1/devices/me/telemetry"
TOPIC_RPC_REQUEST = "v1/devices/me/rpc/request/+"
TOPIC_RPC_RESPONSE = "v1/devices/me/rpc/response/"
TOPIC_ATTRIBUTES = "v1/devices/me/attributes"

TELEMETRY_INTERVAL = 5  # Chu kỳ gửi telemetry (giây)

# Ngưỡng bình thường — giống model TinyML thật
TEMP_RANGE = (25.0, 35.0)
HUMI_RANGE = (60.0, 80.0)


# ==================== TRẠNG THÁI THIẾT BỊ ====================

device_state = {
    "temperature": 28.5,
    "humidity": 65.0,
    "inference_result": 0.12,
    "led": True,
    "neo_led": True,
}


def simulate_anomaly_score(temp: float, humi: float) -> float:
    """Mô phỏng output TinyML (0..1). > 0.5 = bất thường."""
    is_anomalous = (
        temp < TEMP_RANGE[0] or temp > TEMP_RANGE[1] or
        humi < HUMI_RANGE[0] or humi > HUMI_RANGE[1]
    )
    lo, hi = (0.60, 0.95) if is_anomalous else (0.05, 0.30)
    return round(random.uniform(lo, hi), 4)


# ==================== MQTT CALLBACKS ====================

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(TOPIC_RPC_REQUEST)
        print("[SIM] Đã kết nối broker, đang lắng nghe RPC")
    else:
        print(f"[SIM] Kết nối thất bại (rc={rc})")


# Bảng xử lý RPC: method -> (state_key, attribute_key)
_RPC_HANDLERS = {
    "setValueLedBlinky": ("led",     "LedState"),
    "setValueNeoLed":    ("neo_led", "NeoLedState"),
}


def on_message(client, userdata, msg):
    """Xử lý lệnh RPC từ HERA bot."""
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        return

    method = payload.get("method", "")
    params = payload.get("params")
    request_id = msg.topic.split("/")[-1]

    if method not in _RPC_HANDLERS:
        print(f"[SIM] ⚠️ Method không xác định: {method}")
        return

    state_key, attr_key = _RPC_HANDLERS[method]
    device_state[state_key] = bool(params)
    status = "ON" if device_state[state_key] else "OFF"
    icon = "💡" if state_key == "led" else "🌈"
    print(f"[SIM] {icon} {attr_key} → {status}")

    feedback = json.dumps({attr_key: device_state[state_key]})
    client.publish(f"{TOPIC_RPC_RESPONSE}{request_id}", feedback)
    client.publish(TOPIC_ATTRIBUTES, feedback)

#

# ==================== TELEMETRY ====================

def publish_telemetry(client):
    """Gửi dữ liệu cảm biến giả lập theo chu kỳ."""
    while True:
        # Random-walk — mô phỏng drift cảm biến thật
        device_state["temperature"] += random.uniform(-0.3, 0.3)
        device_state["humidity"] += random.uniform(-0.8, 0.8)

        # Giới hạn trong khoảng vật lý hợp lý
        device_state["temperature"] = round(
            max(15.0, min(45.0, device_state["temperature"])), 2
        )
        device_state["humidity"] = round(
            max(30.0, min(95.0, device_state["humidity"])), 2
        )
        device_state["inference_result"] = simulate_anomaly_score(
            device_state["temperature"], device_state["humidity"]
        )

        payload = {
            "temperature": device_state["temperature"],
            "humidity": device_state["humidity"],
            "inference_result": device_state["inference_result"],
            "led_state": device_state["led"],
            "neo_led_state": device_state["neo_led"],
        }
        client.publish(TOPIC_TELEMETRY, json.dumps(payload))

        print(
            f"[SIM] 📡 T={payload['temperature']}°C  "
            f"H={payload['humidity']}%  "
            f"Anomaly={payload['inference_result']}  "
            f"LED={'ON' if payload['led_state'] else 'OFF'}  "
            f"Neo={'ON' if payload['neo_led_state'] else 'OFF'}"
        )
        time.sleep(TELEMETRY_INTERVAL)


# ==================== MAIN ====================

def main():
    print("=" * 50)
    print("   ESP32 IoT Device Simulator")
    print("=" * 50)
    print(f"Broker: {MQTT_BROKER}:{MQTT_PORT} | Interval: {TELEMETRY_INTERVAL}s\n")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "ESP32_Simulator")
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
    except ConnectionRefusedError:
        print("❌ Không kết nối được MQTT broker!")
        print("   Đảm bảo Mosquitto đang chạy trên localhost:1883")
        return

    # Telemetry chạy nền
    threading.Thread(target=publish_telemetry, args=(client,), daemon=True).start()

    print("[SIM] Đang chạy... Ctrl+C để dừng.\n")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[SIM] Đã dừng.")
        client.disconnect()


if __name__ == "__main__":
    main()
