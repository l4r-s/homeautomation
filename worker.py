import json
import paho.mqtt.client as mqtt

from utils import *

config = Config()
devices, zigbee_devices = loadDevices()

def on_connect(client, userdata, flags, rc):
    print('Connected with result code ' + str(rc))

    sub_list = []
    for d in zigbee_devices:
        sub_list.append((str(config['zigbee2mqtt']['topic'] + '/' + d), 0))

    client.subscribe(sub_list)
    print('Subscribed to topics: ' + str(sub_list))

def on_message(client, userdata, msg):
    device = msg.topic.lstrip(config['zigbee2mqtt']['topic'] + '/')

    if not devices.get(device):
        print('received message without matching device. topic: {}, msg: {}'.format(msg.topic, msg.payload))
        return False

    devices[device].update(json.loads(msg.payload))
    print('received: ' + str(msg.topic) + ' ' + str(msg.payload))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(config['zigbee2mqtt']['server'], config['zigbee2mqtt']['port'], 60)
client.loop_forever()

