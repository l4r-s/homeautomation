import time
import graphyte

from utils import *

config = Config()

graphyte.init(config['metrics']['server'], prefix=config['metrics']['prefix'])
log.info('connected to graphite server : ' + config['metrics']['server'])

all_devices, _ = loadDevices()
devices = {}

for d in all_devices:
    if all_devices[d].__dict__.get('metrics'):
        devices[d] = all_devices[d]

# loop
while True:
    for d in devices:
        data = loadDevice(d)

        key_list = ['last_received']
        for k in data.__dict__.keys():
            key_list.append(k)

        for k in key_list:
            if k == 'last_received' or type(data.__dict__[k]) == int or type(data.__dict__[k]) == float:
                name = data.name + '.' + k

                if k == 'last_received':
                    now = time.localtime()
                    unix_now = time.mktime(now)
                    value = unix_now - data.last_update['unix']

                if k != 'last_received':
                    value = data.__dict__[k]

                graphyte.send(name, value)
                log.info('sendet metrics for : ' + name + ' value: ' + str(value))

    time.sleep(config['metrics']['timeout'])
