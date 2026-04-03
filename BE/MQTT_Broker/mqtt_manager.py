## GOM MQTT THÀNH 1 CLASS, BỎ 4 FILE KIA

import asyncio
from amqtt.broker import Broker
import threading
import time
import paho.mqtt.client as mqtt
import json
import random
from pymongo import MongoClient
from datetime import datetime, timezone

client = MongoClient("mongodb://localhost:27017/")
db = client["HERA"]
collection = db["telemetry_points"]

class MQTTManager:
    def __init__(self, broker_address="192.168.1.34", port=1883):
        self.broker_address = broker_address
        self.port = port
        
        # === Cấu hình Broker ===
        self.broker_config = {
            'listeners': {
                'default': {
                    'type': 'tcp',
                    'bind': f'{self.broker_address}:{self.port}'
                }
            },
            'plugins': {
                'amqtt.plugins.authentication.AnonymousAuthPlugin': {},
                'amqtt.plugins.topic_checking.TopicTabooPlugin': {},
                'amqtt.plugins.sys.broker.BrokerSysPlugin': {
                    'sys_interval': 10
                }
            }
        }

        # === Khởi tạo Client ===
        self.client = mqtt.Client()
        # Gắn các hàm callback
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        self.client.on_publish = self.on_publish
        self.latest_sensor_data = {}
        # self.latest_sensor_data = {"temperature": "25"}

    @property
    def sensor_state(self) -> dict:
        """Compatibility property - returns latest_sensor_data"""
        return self.latest_sensor_data

    # --- Các hàm của Broker ---
    def _start_broker_thread(self):
        async def broker_coro():
            broker = Broker(self.broker_config)
            await broker.start()
            print("🟢 MQTT Broker started...")

        # Mỗi thread cần một event loop riêng cho asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(broker_coro())
        loop.run_forever()

    # --- Các hàm Callback của Client ---
    def on_connect(self, client, userdata, flags, rc):
        client.subscribe("#", qos=0)
        # Vừa kết nối xong là đăng ký nhận (subscribe) tất cả các topic (#)
        print("🟢 Client Connected.")

    def on_subscribe(self, client, userdata, mid, granted_qos):
        # Do smth ?
        print("✅ Subscribed successfully.")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')

        if "telemetry" in topic:
            # Log dữ liệu cảm biến nhận được từ ESP32 (để debug)
            # print(f"📊 [Sensor data] {payload}")
            try:
                # Cập nhật dữ liệu mới nhất vào bộ nhớ
                self.latest_sensor_data = json.loads(payload)
                doc = {
                    "recorded_at": datetime.now(timezone.utc),
                    "metadata": {
                        "device_id": "device_0001",
                        "env_id": "env_0001"
                    },
                    **{k: v for k, v in self.latest_sensor_data.items() if v is not None}
                }

                collection.insert_one(doc)
                print(f"💾 [Database] Inserted sensor data: {doc}")
            except Exception as e:
                print("JSON parse error:", e)
        elif "response" in topic:
            print(f"✅ [Feedback circuit] Topic: {topic} | Data: {payload}")
        else:
            pass

    def on_publish(self, client, userdata, mid):
        print(f"📨 Message ID {mid} published successfully")

    # --- Các hàm điều khiển (API cho các file khác gọi) ---
    def start(self):
        """Khởi động Broker trong luồng ẩn và kết nối Client"""
        # Chạy Broker trong một luồng (thread) riêng để không block chương trình chính
        broker_thread = threading.Thread(target=self._start_broker_thread, daemon=True)
        broker_thread.start()

        # Đợi một chút để Broker khởi động xong
        time.sleep(2)

        # Kết nối Client vào Broker
        self.client.connect(self.broker_address, self.port)
        
        # Dùng loop_start() chạy ngầm thay vì loop_forever() để không khóa luồng chính
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
            print("🔴 MQTT Client disconnected")

    def send_rpc_command(self, method_name, params):
        """Hàm dùng để AI gọi khi cần gửi text/lệnh xuống ESP32
        đóng gói data theo dạng JSON """
        request_id = random.randint(1, 10000) # Tạo ID ngẫu nhiên cho mỗi request
        topic = f"v1/devices/me/rpc/request/{request_id}"
        
        # Đóng gói dữ liệu thành JSON
        payload = {
            "method": method_name,
            "params": params
        }
        json_payload = json.dumps(payload)
        
        # Gửi đi
        self.client.publish(topic, json_payload)
        print(f"🚀 [Backend Send] Topic: {topic} | Data: {json_payload}")

    # Alias for HERA compatibility
    def publish_rpc(self, method: str, params):
        """Alias for send_rpc_command() - used by HERA"""
        self.send_rpc_command(method, params)

    def get_sensor_snapshot(self) -> dict:
        """Return a copy of the current sensor state - used by HERA"""
        return dict(self.latest_sensor_data)

# === Cách chạy thử file này ===
if __name__ == "__main__":
    mqtt_system = MQTTManager()
    mqtt_system.start()

    print("🎙️ HERA is ready. Enter a command (type 'exit' to quit):")
    
    try:
        while True:
    #         # Hiển thị Menu cho người dùng
    #         print("\n" + "="*35)
    #         print("📜 SMART HOME CONTROL MENU")
    #         print("1. 💡 Turn on living room light")
    #         print("2. 🌑 Turn off living room light")
    #         print("3. 🌈 Turn on NeoPixel light")
    #         print("4. 🌑 Turn off NeoPixel light")
    #         print("5. 🌡️ View temperature and humidity status")
    #         print("0. ❌ Exit program")
    #         print("="*35)
            
    #         # Lấy lựa chọn từ người dùng
    #         choice = input("👉 Please choose an option (0-5): ").strip()
            
    #         if choice == '0':
    #             print("👋 Exiting program...")
    #             break
                
    #         elif choice == '1':
    #             print("🤖 HERA: Turning on the living room light...")
    #             mqtt_system.send_rpc_command("setValueLedBlinky", True)
                
    #         elif choice == '2':
    #             print("🤖 HERA: Turning off the living room light...")
    #             mqtt_system.send_rpc_command("setValueLedBlinky", False)

    #         elif choice == '3':
    #             print("🤖 HERA: Turning on the NeoPixel light...")
    #             mqtt_system.send_rpc_command("setValueNeoLed", True)
                
    #         elif choice == '4':
    #             print("🤖 HERA: Turning off the NeoPixel light...")
    #             mqtt_system.send_rpc_command("setValueNeoLed", False)
                
    #         elif choice == '5':
    #             if hasattr(mqtt_system, 'latest_sensor_data') and mqtt_system.latest_sensor_data:
    #                 temp = mqtt_system.latest_sensor_data.get("temperature", "Not updated yet")
    #                 hum = mqtt_system.latest_sensor_data.get("humidity", "Not updated yet")
    #                 print(f"🤖 SENSOR INFO: Current temperature is {temp}°C, humidity is {hum}%.")
    #             else:
    #                 print("🤖 SENSOR INFO: Waiting for the board to send data, please try again in a few seconds...")
                
    #         else:
    #             print("⚠️ Invalid choice. Please enter a number from 0 to 5.")
            None
    except KeyboardInterrupt:
        print("Closing connection...")
        mqtt_system.client.disconnect()