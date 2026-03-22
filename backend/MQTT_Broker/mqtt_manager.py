## GOM MQTT THÀNH 1 CLASS, BỎ 4 FILE KIA

import asyncio
from amqtt.broker import Broker
import threading
import time
import paho.mqtt.client as mqtt
import json
import random

class MQTTManager:
    def __init__(self, broker_address="127.0.0.1", port=1884):
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
        print("✅ Subscribed successfully.")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')

        if "telemetry" in topic:
            print(f"📊 [Sensor data] {payload}")
            try:
                # Cập nhật dữ liệu mới nhất vào bộ nhớ
                self.latest_sensor_data = json.loads(payload)
            except Exception as e:
                print("Lỗi parse JSON:", e)
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

# === Cách chạy thử file này ===
if __name__ == "__main__":
    mqtt_system = MQTTManager()
    mqtt_system.start()

    print("🎙️ HERA đã sẵn sàng. Hãy nhập lệnh (Gõ 'exit' để thoát):")
    
    try:
        while True:
            # Hiển thị Menu cho người dùng
            print("\n" + "="*35)
            print("📜 MENU ĐIỀU KHIỂN NHÀ THÔNG MINH")
            print("1. 💡 Bật đèn phòng khách")
            print("2. 🌑 Tắt đèn phòng khách")
            print("3. 🌈 Bật đèn màu (NeoPixel)")
            print("4. 🌑 Tắt đèn màu (NeoPixel)")
            print("5. 🌡️ Xem trạng thái nhiệt độ, độ ẩm")
            print("0. ❌ Thoát chương trình")
            print("="*35)
            
            # Lấy lựa chọn từ người dùng
            choice = input("👉 Mời bạn chọn chức năng (0-5): ").strip()
            
            if choice == '0':
                print("👋 Đang thoát chương trình...")
                break
                
            elif choice == '1':
                print("🤖 HERA: Đang bật đèn phòng khách...")
                mqtt_system.send_rpc_command("setValueLedBlinky", True)
                
            elif choice == '2':
                print("🤖 HERA: Đang tắt đèn phòng khách...")
                mqtt_system.send_rpc_command("setValueLedBlinky", False)

            elif choice == '3':
                print("🤖 HERA: Đang bật đèn NeoPixel...")
                mqtt_system.send_rpc_command("setValueNeoLed", True)
                
            elif choice == '4':
                print("🤖 HERA: Đang tắt đèn NeoPixel...")
                mqtt_system.send_rpc_command("setValueNeoLed", False)
                
            elif choice == '5':
                if hasattr(mqtt_system, 'latest_sensor_data') and mqtt_system.latest_sensor_data:
                    temp = mqtt_system.latest_sensor_data.get("temperature", "Chưa cập nhật")
                    hum = mqtt_system.latest_sensor_data.get("humidity", "Chưa cập nhật")
                    print(f"🤖 THÔNG TIN SENSOR: Nhiệt độ hiện tại là {temp}°C, Độ ẩm là {hum}%.")
                else:
                    print("🤖 THÔNG TIN SENSOR: Đang chờ mạch gửi dữ liệu lên, vui lòng thử lại sau vài giây...")
                
            else:
                print("⚠️ Lựa chọn không hợp lệ. Vui lòng nhập số từ 0 đến 5.")
    except KeyboardInterrupt:
        print("Đang đóng kết nối...")
        mqtt_system.client.disconnect()