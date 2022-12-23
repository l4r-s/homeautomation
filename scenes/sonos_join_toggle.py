#!/bin/python
import os
import sys
import time
from soco import SoCo

sys.path.insert(1, os.path.join(sys.path[0], '..'))
from utils import *

device_name = sys.argv[1]
sonos = loadDevice(device_name)
sonos.doToggleJoin()
