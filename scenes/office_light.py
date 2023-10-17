#!/bin/python
import os
import sys
import time

sys.path.insert(1, os.path.join(sys.path[0], '..'))
from utils import *

office1 = loadDevice('office1')
office1.setState('toggle')

