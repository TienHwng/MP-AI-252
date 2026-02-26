import asyncio
from turtledemo.forest import start

from hbmqtt.broker import Broker
import threading
import time
import paho.mqtt.client as mqtt

# === Broker Configuration ===
broker_config = {
    'listeners': {
        'default': {
            'type': 'tcp',
            'bind': '0.0.0.0:1883'
        }
    },
    'sys_interval': 10,
    'auth': {
        'allow-anonymous': True   # <-- Disable anonymous!
        #'plugins': ['auth_file'],   # <-- Use file-based auth
        #'password-file': 'password_file.txt',  # <-- Point to your password file
        #'plugins': ['allow_all_auth']

    },
    'topic-check': {
        'enabled': True,
        'plugins': ['topic_taboo']
    }
}

def start_broker():
    async def broker_coro():
        broker = Broker(broker_config)
        await broker.start()
        print("MQTT Broker started...")

    # Each thread needs its own event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(broker_coro())
    loop.run_forever()

# === MQTT Subscriber (in thread) ===
def run_subscriber():
    broker_address = "127.0.0.1"
    topic = "#" #subscribe to all topics

    def on_message(client, userdata, msg):
        print("Received:", msg.topic, msg.payload.decode("utf-8"))

    def on_subscribe(client, userdata, mid, granted_qos):
        print("✅ Subscribed successfully.")

    def on_connect(client, userdata, flags, rc):
        print("Connected.")
        client.subscribe(topic, qos=0)

    client = mqtt.Client("PythonSubscriber")
    client.on_message = on_message
    client.on_subscribe = on_subscribe
    client.on_connect = on_connect

    # Wait a bit for the broker to start
    time.sleep(2)

    client.connect(broker_address, 1883)
    client.loop_forever()

if __name__ == "__main__":
    # Broker in one thread
    broker_thread = threading.Thread(target=start_broker, daemon=True)
    broker_thread.start()

    # Subscriber in another thread
    subscriber_thread = threading.Thread(target=run_subscriber, daemon=True)
    subscriber_thread.start()


    # Keep the main program alive
    while True:
        time.sleep(1)