import paho.mqtt.client as mqtt

broker_address = "127.0.0.1"
topic = "#"  #listen to all topics

def on_message(client, userdata, msg):
    print("Received:",msg.topic, msg.payload.decode("utf-8"))

def on_subscribe(client, userdata, mid, granted_qos):
    print("✅ Subscribed successfully.")

def on_connect(client, userdata, flags, rc):
    print("Connected.")
    client.subscribe(topic, qos=0)

client = mqtt.Client("PythonSubscriber")
client.on_message = on_message
client.on_subscribe = on_subscribe
client.on_connect = on_connect


client.connect(broker_address, 1883)
client.loop_forever()