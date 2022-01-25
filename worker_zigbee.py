import json
import paho.mqtt.client as mqtt

from utils import *

config = Config()
devices, zigbee_devices = loadDevices('zigbee')

def on_connect(client, userdata, flags, rc):
    log.info('Connected with result code ' + str(rc))

    sub_list = []
    for d in zigbee_devices.keys():
        sub_list.append((str(config['zigbee2mqtt']['topic'] + '/' + zigbee_devices[d].zigbee_id), 0))

    client.subscribe(sub_list)

    for sub in sub_list:
        log.info('Subscribed to topic: ' + str(sub[0]))

def on_message(client, userdata, msg):
    zigbee_id = msg.topic.lstrip(config['zigbee2mqtt']['topic'] + '/')

    device = None

    for d in zigbee_devices:
        if zigbee_id == devices[d].zigbee_id:
            device = loadDevice(d)

    if not device:
        log.error('received message without matching device. topic: {}, msg: {}'.format(msg.topic, msg.payload))
        return False

    device.receiveMsg(json.loads(msg.payload))
    log.info('received: ' + str(msg.topic) + ' ' + str(msg.payload))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(config['zigbee2mqtt']['server'], config['zigbee2mqtt']['port'], 60)
client.loop_forever()

