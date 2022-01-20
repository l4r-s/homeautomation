import time
from utils import *

config = Config()
devices, http_devices = loadDevices('http')

while True:
    for d in http_devices:
        log.info(d)
        out = devices[d].getState()

        #if not e:
        #    log.error('{} - getState() was not sucessfull'.format(d))
        #    continue

        log.info('INFO - {} - getState(): {}'.format(d, out))

    time.sleep(config['http_worker']['interval'])

