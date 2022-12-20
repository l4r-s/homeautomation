#!/bin/python
import os
import sys
import time
from soco import SoCo

sys.path.insert(1, os.path.join(sys.path[0], '..'))
from utils import *

sonos = loadDevice('sonos_kueche')
sonos.setVolume(sonos.volume + 1)
