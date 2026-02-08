print("Hello Core IOT Device 2!")

import paho.mqtt.client as mqttclient
import time
import json

BROKER_ADDRESS = "app.coreiot.io"
PORT = 1883
ACCESS_TOKEN = "S1YzYLnmuvkEcoYgACVp"
ACCESS_USERNAME = "hwng_device_2"
ACCESS_PASSWORD = "12345678"

def subscribed(client, userdata, mid, granted_qos):
    print("Subscribed...")


def recv_message(client, userdata, message):
    print("Received: ", message.payload.decode("utf-8"))
    temp_data = {'value': True}
    try:
        jsonobj = json.loads(message.payload)
        if jsonobj['method'] == "setValueLed2":
            temp_data['value'] = jsonobj['params']
            client.publish('v1/devices/me/attributes', json.dumps(temp_data), 1)
    except:
        pass


def connected(client, usedata, flags, rc):
    if rc == 0:
        print("Connected successfully!!")
        client.subscribe("v1/devices/me/rpc/request/+")
    else:
        print("Connection is failed")


client = mqttclient.Client("IOT_DEVICE_2")
client.username_pw_set(username=ACCESS_TOKEN, password="")

client.on_connect = connected
client.connect(BROKER_ADDRESS, PORT, keepalive=60)
client.loop_start()

client.on_subscribe = subscribed
client.on_message = recv_message

temp = 10
humi = 30
light_intesity = 100
counter = 0

# #HCMUT
# long = 106.65789107082472
# lat = 10.772175109674038

#H6
long = 106.80633605864662
lat = 10.880018410410052

while True:
    collect_data = {'temperature': temp, 'humidity': humi, 
                    'light':light_intesity,
                    'long': long, 'lat': lat}
    temp += 1
    humi += 1
    light_intesity += 1
    client.publish('v1/devices/me/telemetry', json.dumps(collect_data), 1)
    time.sleep(5)