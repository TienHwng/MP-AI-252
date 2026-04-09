## GOM MQTT THÀNH 1 CLASS, BỎ 4 FILE KIA

import asyncio
import copy
import json
import random
import threading
import time

import paho.mqtt.client as mqtt
from amqtt.broker import Broker

# Set to True to enable MongoDB integration, False to disable
ENABLE_MONGODB = True

if ENABLE_MONGODB:
    from pymongo import MongoClient
    from datetime import datetime, timezone

    mongo_client = MongoClient("mongodb://localhost:27017/")
    db = mongo_client["HERA"]
    collection = db["telemetry_points"]

class MQTTManager:
    def __init__(self, broker_address="172.20.10.2", port=1883):
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

    @staticmethod
    def _normalize_sensor_payload(payload: dict) -> dict:
        if not isinstance(payload, dict):
            return {}

        network = payload.get("network") if isinstance(payload.get("network"), dict) else {}
        devices = payload.get("devices") if isinstance(payload.get("devices"), dict) else {}
        sensors = payload.get("sensors") if isinstance(payload.get("sensors"), dict) else {}

        return {
            "network": {
                "wifi_connected": network.get("wifi_connected"),
                "wifi_rssi": network.get("wifi_rssi"),
                "wifi_ip": network.get("wifi_ip"),
                "mqtt_connected": network.get("mqtt_connected"),
                "uptime_ms": network.get("uptime_ms"),
            },
            "devices": {
                "led_status": devices.get("led_status"),
                "neo_led_status": devices.get("neo_led_status"),
                "ws2812_status": devices.get("ws2812_status"),
                "relay_status": devices.get("relay_status"),
                "mini_fan_status": devices.get("mini_fan_status"),
            },
            "sensors": {
                "temperature": sensors.get("temperature"),
                "humidity": sensors.get("humidity"),
                "light": sensors.get("light"),
                "anomaly": sensors.get("anomaly"),
            },
        }

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
                
                # self.latest_sensor_data = json.loads(payload)

                parsed = json.loads(payload)
                self.latest_sensor_data = self._normalize_sensor_payload(parsed)

                if ENABLE_MONGODB:
                    doc = {
                        "recorded_at": datetime.now(timezone.utc),
                        "metadata": {
                            "device_id": "device_0001",
                            "env_id": "env_0001"
                        },
                        **{k: v for k, v in self.latest_sensor_data.items() if v is not None}
                    }

                    collection.insert_one(doc)
                    # print(f"💾 [Database] Inserted sensor data: {doc}")

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
        return copy.deepcopy(self.latest_sensor_data)

# === Cách chạy thử file này ===
if __name__ == "__main__":
    mqtt_system = MQTTManager()
    mqtt_system.start()

    print("🎙️ HERA is ready. Enter a command (type 'exit' to quit):")
    
    try:
        while True:
            # Hiển thị Menu cho người dùng
            print("\n" + "="*35)
            print("📜 SMART HOME CONTROL MENU")
            print("1. 💡 Turn on living room light")
            print("2. 🌑 Turn off living room light")
            print("3. 🌈 Turn on NeoPixel light")
            print("4. 🌑 Turn off NeoPixel light")
            print("5. 🎇 Turn on WS2812 light")
            print("6. 🌑 Turn off WS2812 light")
            print("7. 🌀 Turn on mini fan")
            print("8. 🌑 Turn off mini fan")
            print("9. 🔌 Turn on relay")
            print("10. 🌑 Turn off relay")
            print("11. 🌡️ View sensors status")
            print("12. 💡 View devices status")
            print("13. 📶 View network status")
            print("14. 📦 View full telemetry data")
            print("0. ❌ Exit program")
            print("="*35)
            
            # Lấy lựa chọn từ người dùng
            choice = input("👉 Please choose an option (0-14): ").strip()
            
            if choice == '0':
                print("👋 Exiting program...")
                break
                
            elif choice == '1':
                print("🤖 HERA: Turning on the living room light...")
                mqtt_system.send_rpc_command("setValueLedBlinky", True)
                
            elif choice == '2':
                print("🤖 HERA: Turning off the living room light...")
                mqtt_system.send_rpc_command("setValueLedBlinky", False)

            elif choice == '3':
                print("🤖 HERA: Turning on the NeoPixel light...")
                mqtt_system.send_rpc_command("setValueNeoLed", True)
                
            elif choice == '4':
                print("🤖 HERA: Turning off the NeoPixel light...")
                mqtt_system.send_rpc_command("setValueNeoLed", False)

            elif choice == '5':
                print("🤖 HERA: Turning on WS2812 light...")
                mqtt_system.send_rpc_command("setValueWS2812", True)

            elif choice == '6':
                print("🤖 HERA: Turning off WS2812 light...")
                mqtt_system.send_rpc_command("setValueWS2812", False)

            elif choice == '7':
                print("🤖 HERA: Turning on mini fan...")
                mqtt_system.send_rpc_command("setValueMiniFan", True)

            elif choice == '8':
                print("🤖 HERA: Turning off mini fan...")
                mqtt_system.send_rpc_command("setValueMiniFan", False)

            elif choice == '9':
                print("🤖 HERA: Turning on relay...")
                mqtt_system.send_rpc_command("setValueRelay", True)

            elif choice == '10':
                print("🤖 HERA: Turning off relay...")
                mqtt_system.send_rpc_command("setValueRelay", False)
                
            elif choice == '11':
                if hasattr(mqtt_system, 'latest_sensor_data') and mqtt_system.latest_sensor_data:
                    sensors = mqtt_system.latest_sensor_data.get("sensors", {})
                    temp = sensors.get("temperature", "Not updated yet")
                    hum = sensors.get("humidity", "Not updated yet")
                    light = sensors.get("light", "Not updated yet")

                    print(f"🤖 SENSOR INFO:")
                    print(f"   - Temperature: {temp}°C")
                    print(f"   - Humidity: {hum}%")
                    print(f"   - Light: {light}")
                else:
                    print("🤖 SENSOR INFO: Waiting for the board to send data, please try again in a few seconds...")

            elif choice == '12':
                if hasattr(mqtt_system, 'latest_sensor_data') and mqtt_system.latest_sensor_data:
                    devices = mqtt_system.latest_sensor_data.get("devices", {})
                    led = devices.get("led_status", "Unknown")
                    neo = devices.get("neo_led_status", "Unknown")
                    ws2812 = devices.get("ws2812_status", "Unknown")
                    relay = devices.get("relay_status", "Unknown")
                    fan = devices.get("mini_fan_status", "Unknown")

                    print("🤖 DEVICE STATUS:")
                    print(f"   - LED: {led}")
                    print(f"   - NeoPixel: {neo}")
                    print(f"   - WS2812: {ws2812}")
                    print(f"   - Relay: {relay}")
                    print(f"   - Mini fan: {fan}")
                else:
                    print("🤖 DEVICE STATUS: Waiting for telemetry...")

            elif choice == '13':
                if hasattr(mqtt_system, 'latest_sensor_data') and mqtt_system.latest_sensor_data:
                    network = mqtt_system.latest_sensor_data.get("network", {})
                    wifi_connected = network.get("wifi_connected", "Unknown")
                    wifi_rssi = network.get("wifi_rssi", "Unknown")
                    wifi_ip = network.get("wifi_ip", "Unknown")
                    mqtt_connected = network.get("mqtt_connected", "Unknown")
                    uptime_ms = network.get("uptime_ms", "Unknown")

                    print("🤖 NETWORK STATUS:")
                    print(f"   - WiFi connected: {wifi_connected}")
                    print(f"   - WiFi RSSI: {wifi_rssi} dBm")
                    print(f"   - WiFi IP: {wifi_ip}")
                    print(f"   - MQTT connected: {mqtt_connected}")
                    print(f"   - Uptime: {uptime_ms} ms")
                else:
                    print("🤖 NETWORK STATUS: Waiting for telemetry...")

            elif choice == '14':
                if hasattr(mqtt_system, 'latest_sensor_data') and mqtt_system.latest_sensor_data:
                    print("🤖 FULL TELEMETRY DATA:")
                    print(json.dumps(mqtt_system.latest_sensor_data, indent=2, ensure_ascii=False))
                else:
                    print("🤖 FULL TELEMETRY: Waiting for telemetry...")
                
            else:
                print("⚠️ Invalid choice. Please enter a number from 0 to 14.")
            None
    except KeyboardInterrupt:
        print("Closing connection...")
    finally:
        mqtt_system.client.disconnect()