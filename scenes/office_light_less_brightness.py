#!/bin/python
import os
import sys
import time

sys.path.insert(1, os.path.join(sys.path[0], '..'))
from utils import *

office1 = loadDevice('office1')

b = office1.brightness - 10
if b == 0:
    b = 1

r,_ = office1.setBrightness(b)

if not r or b == 1:
    office1.action("effect",{"effect": "blink"})
