import time
from utils import *

config = Config()
devices, http_devices = loadDevices('http')

while True:
    for d in http_devices:
        print(d)
        e, out = devices[d].getState()

        if not e:
            print('ERROR - {} - getState() was not sucessfull'.format(d))
            continue

        print('INFO - {} - getState(): {}'.format(d, out))

    time.sleep(config['http_worker']['interval'])

