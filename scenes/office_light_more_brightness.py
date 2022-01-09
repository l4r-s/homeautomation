#!/bin/python
import os
import sys
import time

sys.path.insert(1, os.path.join(sys.path[0], '..'))
from utils import *

office1 = loadDevice('office1')
r,_ = office1.setBrightness(office1.brightness + 10)

if not r:
    office1.action("effect",{"effect": "blink"})
