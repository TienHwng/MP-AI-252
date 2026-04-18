import paho.mqtt.client as mqtt
import time
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV_PATH)

broker_address = os.getenv("MQTT_BROKER")
broker_port = int(os.getenv("MQTT_PORT"))
topic = "/test/topic1"


def on_connect(client, userdata, flags, rc):
	print("Connected.")


def on_publish(client, userdata, mid):
	print(f"[ OK ] Message ID {mid} published successfully")


# client = mqtt.Client("PythonPublisher")
client = mqtt.Client()
mqtt_username = os.getenv("MQTT_USERNAME")
mqtt_password = os.getenv("MQTT_PASSWORD")
if mqtt_username:
	client.username_pw_set(mqtt_username, mqtt_password)
client.on_connect = on_connect
client.on_publish = on_publish
client.connect(broker_address, broker_port)
client.loop_start()

while True:
	client.publish(topic, "ABC .....")
	print("Sent a message")
	time.sleep(5)
client.disconnect()
