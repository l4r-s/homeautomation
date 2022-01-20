#!/bin/python
import os
import sys
import time

sys.path.insert(1, os.path.join(sys.path[0], '..'))
from utils import *

volumio = loadDevice('volumio')

if not volumio.online:
    log.info("Volumio is not online, exiting...")
    sys.exit(0)

volumio.setVolume(volumio.volume - 5)
