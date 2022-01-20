#!/bin/python
import os
import sys
import time

sys.path.insert(1, os.path.join(sys.path[0], '..'))
from utils import *

switch = loadDevice('music_switch')
volumio = loadDevice('volumio')


# if already online and playing, we stop volumio playback
if switch.relay:
    if volumio.status == 'play':
        volumio.sendCmd('stop')
        sys.exit(0)

switch.setState('on')

while not volumio.online:
    volumio.getState()
    log.info("Waiting for Volumio to come online")
    time.sleep(2)

volumio.setVolume(40)
volumio.sendCmd('toggle')
