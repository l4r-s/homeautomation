#!/bin/python
import os
import sys
import time

sys.path.insert(1, os.path.join(sys.path[0], '..'))
from utils import *

switch = loadDevice('music_switch')
switch.setState('off')

