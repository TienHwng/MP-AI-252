import paho.mqtt.client as mqtt
import time
import json
import random
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV_PATH)

# === CẤU HÌNH KẾT NỐI ===
BROKER_ADDRESS = os.getenv("MQTT_BROKER")
PORT = int(os.getenv("MQTT_PORT"))

# Các topic giống hệt file C++
TOPIC_TELEMETRY = "v1/devices/me/telemetry"
TOPIC_RPC_REQUEST = "v1/devices/me/rpc/request/+"
TOPIC_RPC_RESPONSE = "v1/devices/me/rpc/response/"

# Trạng thái thiết bị giả lập
device_state = {
    "led_blinky": False,
    "neo_led": False
}

# === CÁC HÀM CALLBACK CỦA MQTT ===
def on_connect(client, userdata, flags, rc):
    print("[OK] [ESP32 Simulator] Đã kết nối thành công tới HERA Broker!")
    # Đăng ký nhận lệnh từ HERA
    client.subscribe(TOPIC_RPC_REQUEST)
    print(f"[INFO] [ESP32 Simulator] Đang lắng nghe lệnh tại: {TOPIC_RPC_REQUEST}")

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    print(f"\n[INFO] [ESP32 Simulator] Nhận lệnh từ HERA: {payload}")
    
    try:
        # Đọc JSON HERA gửi xuống
        data = json.loads(payload)
        method = data.get("method")
        params = data.get("params")
        
        # Lấy request_id từ topic (VD: v1/devices/me/rpc/request/123 -> lấy 123)
        request_id = topic.split('/')[-1]
        
        # Xử lý lệnh y hệt C++
        response_doc = {}
        if method == "setValueLedBlinky":
            device_state["led_blinky"] = params
            print("[ACTION]", f"Đã {'BẬT' if params else 'TẮT'} LED thường.")
            response_doc["LedState"] = params
            
        elif method == "setValueNeoLed":
            device_state["neo_led"] = params
            print("[ACTION]", f"Đã {'BẬT' if params else 'TẮT'} NeoPixel.")
            response_doc["NeoLedState"] = params

        # Gửi phản hồi (response) lại cho HERA
        response_topic = f"{TOPIC_RPC_RESPONSE}{request_id}"
        client.publish(response_topic, json.dumps(response_doc))
        print(f"[INFO] [ESP32 Simulator] Đã gửi phản hồi: {json.dumps(response_doc)}")
        
    except json.JSONDecodeError:
        print("[ ERROR ] [ESP32 Simulator] Lỗi: Không thể đọc được JSON!")

# === KHỞI TẠO VÀ CHẠY MẠCH GIẢ LẬP ===
client = mqtt.Client("ESP32_Simulator_Client")
client.on_connect = on_connect
client.on_message = on_message

print("[INFO] Khởi động Mạch ESP32 Giả lập...")
client.connect(BROKER_ADDRESS, PORT)

# Chạy loop_start để mạch lắng nghe ngầm mà không khóa vòng lặp chính
client.loop_start()

try:
    while True:
        # Tạo dữ liệu cảm biến giả (random cho sinh động)
        temp = round(random.uniform(25.0, 32.0), 1)
        hum = round(random.uniform(50.0, 80.0), 1)
        anomaly = 0.12 # Mô phỏng TinyML
        
        # Đóng gói dữ liệu Telemetry
        telemetry_data = {
            "temperature": temp,
            "humidity": hum,
            "inference_result": anomaly,
            "led_state": device_state["led_blinky"],
            "neo_led_state": device_state["neo_led"]
        }
        
        # Gửi lên HERA
        client.publish(TOPIC_TELEMETRY, json.dumps(telemetry_data))
        # print(f"[ INFO ] [ESP32 Simulator] Gửi Telemetry: {telemetry_data}") 
        # (Em có thể bỏ comment dòng print trên nếu muốn xem chi tiết mạch gửi gì)
        
        # Mạch gửi dữ liệu mỗi 5 giây
        time.sleep(5)
        
except KeyboardInterrupt:
    print("\n[INFO] Tắt mạch giả lập...")
    client.disconnect()
