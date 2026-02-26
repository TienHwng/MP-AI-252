import paho.mqtt.client as mqtt
import time

broker_address = "127.0.0.1"
topic = "/test/topic1"


def on_connect(client, userdata, flags, rc):
    print("Connected.")


def on_publish(client, userdata, mid):
    print(f"📨 Message ID {mid} published successfully")


#client = mqtt.Client("PythonPublisher")
client = mqtt.Client()
client.username_pw_set("mqttclient", "12345678")
client.on_connect = on_connect
client.on_publish = on_publish
client.connect(broker_address, 1883)
client.loop_start()

while True:
    client.publish(topic, "ABC .....")
    print("Sent a message")
    time.sleep(5)
client.disconnect()