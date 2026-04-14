import paho.mqtt.client as mqtt
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV_PATH)

broker_address = os.environ["MQTT_BROKER"]
broker_port = int(os.environ["MQTT_PORT"])
topic = "#"  #listen to all topics

def on_message(client, userdata, msg):
    print("Received:",msg.topic, msg.payload.decode("utf-8"))

def on_subscribe(client, userdata, mid, granted_qos):
    print(" Subscribed successfully.")

def on_connect(client, userdata, flags, rc):
    print("Connected.")
    client.subscribe(topic, qos=0)

client = mqtt.Client("PythonSubscriber")
client.on_message = on_message
client.on_subscribe = on_subscribe
client.on_connect = on_connect


client.connect(broker_address, broker_port)
client.loop_forever()
