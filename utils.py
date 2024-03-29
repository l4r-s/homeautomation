import os
import sys
import time
import json
import yaml
import logging
import requests
import subprocess
import paho.mqtt.client as mqtt
import soco

##
# Config
##

def Config():
    dir_path = os.path.dirname(os.path.realpath(__file__))

    main_config_path = dir_path + '/config.yml'
    additional_config_path = dir_path + '/conf.d/'

    # load main config
    config = {}
    if os.path.isfile(main_config_path):
        with open(main_config_path, 'r') as f:
            config = yaml.safe_load(f)

    # load additional config files
    if os.path.exists(additional_config_path):
        additional_config = os.listdir(additional_config_path)

        for file in additional_config:
            file_extension = file.split('.')[-1]

            if file == 'config.yml':
                continue

            if not (file_extension == 'yml' or file_extension == 'yaml'):
                continue

            with open(additional_config_path + file, 'r') as f:
                c = yaml.safe_load(f)

            #for token in c['api_tokens']:
            #    config['api_tokens'].append(token)

            config.update(c)

    ## generate api_tokens_list
    #config['api_tokens_list'] = []

    #for key in config['api_tokens'].keys():
    #    config['api_tokens_list'].append(config['api_tokens'][key]['token'])

    return config

##
# logger
##

def logger(name=''):
    config = Config()

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)


    # file handlers
    if 'logfile' in config:
        fh = logging.FileHandler(config['logfile'])
        fh.setLevel(level=logging.INFO)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger

log = logger()

##
# Device loading
##

def getDeviceClass(dev_type='default'):
    class_lookup = {
        'default': Device,
        'mystrom_switch': MyStromSwitch,
        'ikea_lamp': IkeaLamp,
        'ikea_switch': IkeaSwitch,
        'ikea_button': IkeaBaseButton,
        'zigbee_log': ZigBeeLogDevice,
        'lora_log': LoraLogDevice,
        'volumio': Volumio,
        'fingerbot': Fingerbot,
        'sonos': Sonos
    }

    return class_lookup.get(dev_type, Device)

def loadDevice(name):
    config = Config()

    device = config['devices'].get(name, None)

    if not device:
        log.error('device {} not found in config!'.format(name))
        return False

    return getDeviceClass(config['devices'][name]['type'])(name)

def loadDevices(com_type=None):
    # type:
    #  - zigbee
    #  - http
    #  - lora

    config = Config()

    devices = {}
    filtered = {}

    for device in config['devices'].keys():
        devices[device] = getDeviceClass(config['devices'][device]['type'])(device)

        if com_type:
            if devices[device].com_type == com_type:
                filtered[device] = devices[device]

        if not com_type:
            filtered = devices

    return devices, filtered


##
# Device Classes
##

class Device():
    def __init__(self, name, data=False):
        self.name = name
        self.com_type = None
        self.actions = []

        self.load()

        if data:
            self.__dict__.update(data)

    def __repr__(self):
        return json.dumps(self.__dict__)

    def getState(self):
        log.error('This device state can only be updated with the .update() method!')
        return False, None

    def updateData(self, data):
        self.setLastUpdate()
        self.__dict__.update(data)

        self.save()

    def setLastUpdate(self):
        now = time.localtime()

        self.last_update = {}
        self.last_update['unix'] = time.mktime(now)
        self.last_update['human'] = time.asctime(now)

    def load(self):
        config = Config()

        storage_directory = config['storage_directory']
        devices = config['devices']
        filename = storage_directory.rstrip('/') + '/' + self.name + '.json'

        self._config = devices[self.name]

        data = {}
        name = self.name

        if os.path.isfile(filename):
            with open(filename) as f:
                data = json.load(f)

        data.update(devices[self.name])

        self.__dict__.update(data)
        self.name = name

        if self.__dict__.get('max_last_update_diff'):
            now = time.mktime(time.localtime())
            max_diff = now - data['max_last_update_diff']

            if self.__dict__.get('last_update', None):
                if self.__dict__['last_update'].get('unix', None):
                    if self.__dict__['last_update']['unix'] < max_diff:
                        self.__dict__['last_update']['outdated'] = True


    def save(self):
        config = Config()

        storage_directory = config['storage_directory']
        devices = config['devices']
        filename = storage_directory.rstrip('/') + '/' + self.name + '.json'

        with open(filename, 'w') as f:
            json.dump(self.__dict__, f)

        return

class Volumio(Device):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.com_type = 'http'
        self.actions = [ 'pause', 'stop', 'toggle', 'volume', 'prev', 'next', 'getState' ]
        self.getState()

    def _get(self, path, fail=True):
        url = 'http://{}/{}'.format(self.address, path.lstrip('/'))
        error = False
        r = None

        try:
            r = requests.get(url, timeout=3)
        except:
            error = True

        if r:
            if r.status_code != 200:
                error = True

        if error:
            self.online = False

            if fail:
                log.error('http request to {} not 200: {} - '.format(url, str(r.status_code), str(r.text)))

            return { 'online': False }

        data = r.json()
        self.online = True

        return data

    def action(self, action, msg=None):
        if action not in self.actions:
            log.error('{} is not allowed ({})'.format(action, str(self.actions)))
            return False, None

        if action == 'pause' or action == 'stop' or action == 'toggle' or action == 'prev' or action == 'next':
            data = self.sendCmd(action)

        if action == 'volume':
            if type(msg) != int:
                log.error('msg must be an integer, desired volume')
                return False, None

            data = self.setVolume(msg)

        if action == 'getState':
            data = self.getState()

        return data

    def setVolume(self, volume=10):
        data = self._get('api/v1/commands/?cmd=volume&volume={}'.format(volume))
        self.volume = volume

        self.save()

        return { 'volume': volume }

    def sendCmd(self, action, params = None):
        if not params:
            data = self._get('api/v1/commands/?cmd={}'.format(action))

        if params:
            data = self._get('api/v1/commands/?cmd={}&{}'.format(action, params))

        self.updateData(data)
        return data

    def getState(self):
        data = self._get('api/v1/getState', fail=False)
        self.updateData(data)

        return data

class Sonos(Device):
    def __init__(self, *args, **kwargs):
        self.transport_info = {}
        self.player = []
        self.joined = False
        self.ip = None

        super().__init__(*args, **kwargs)

        self.com_type = 'http'
        self.actions = [ 'toggle', 'volume', 'getState', 'join', 'unjoin' ]
        self.actions = {
            'toggle': {
                'type': 'button',
                'label': 'Toogle'
            },

            'join': {
                'type': 'button',
                'label': 'Join'
            },

             'unjoin': {
                'type': 'button',
                'label': 'Un-join'
            },

            'volume': {
                'type': 'slider',
                'min': 1,
                'max': 100,
            },


            'getState': {
                'type': 'button',
                'label': 'Refresh data'
            }
        }

        self.getState()

    def action(self, action, msg=None):
        data = {}

        if action not in self.actions:
            log.error('{} is not allowed ({})'.format(action, str(self.actions)))
            return False, None

        if action == 'toggle':
            self.doToggle()

        if action == 'join':
            if self.join_to is defined:
                self.doJoin()

            if self.join_to is not defined:
                log.error('{} is not allowed because device does not have a join_to key'.format(action))

        if action == 'unjoin':
            self.doUnJoin()

        if action == 'volume':
            if type(msg) != int:
                log.error('msg must be an integer, desired volume')
                return False, None

            data = self.setVolume(msg)

        if action == 'getState':
            data = self.getState()

        return data

    def blink(self, player_ip, num=1):
        player = soco.SoCo(player_ip)
        i = 0

        while i < num:
            player.status_light = False
            player.status_light = True
            time.sleep(0.3)
            player.status_light = False
            i += 1

    def doToggleJoin(self):
        if self.joined:
            self.doUnJoin()
        else:
            self.doJoin()

    def doJoin(self):
        player = soco.SoCo(self.ip)

        for p in self.players:
            join_player = soco.SoCo(p)
            if join_player._player_name == self.join_to:
                player.join(join_player)
                self.joined = True

    def doUnJoin(self):
        player = soco.SoCo(self.ip)
        player.unjoin()
        self.joined = False
        self.save()

    def doToggle(self):
        for p in self.coordinators:
            player = soco.SoCo(p)
            state = self.transport_info['current_transport_state']

            if state == 'STOPPED':
                self.blink(p, 3)
                player.volume = self.volume
                player.play()

            if state == 'PLAYING':
                player.pause()

        self.save()

        return { 'play_state': self.transport_info['current_transport_state'] }

    def setVolume(self, volume=10):
        self.volume = volume

        for p in self.coordinators:
            player = soco.SoCo(p)
            player.volume = self.volume
            self.blink(p)

        for p in self.players:
            player = soco.SoCo(p)
            player.volume = self.volume
            self.blink(p)

        self.save()

        return { 'volume': volume }

    def getState(self):
        data = { 'online': True }
        zones = soco.discover()

        if not zones:
            data = { 'online': False }
            log.error('No sonos controller found!')

        if zones:
            self.players = []
            self.coordinators = []

            for z in zones:
                self.players.append(z.ip_address)

                # skip player if it is not the zone we want
                if z._player_name != self.player_name:
                    continue

                if not z._is_coordinator:
                    self.joined = True

                self.ip = z.ip_address
                self.transport_info = z.get_current_transport_info()

                if z._is_coordinator:
                    self.coordinators.append(z.ip_address)
                    self.volume = z.volume

        self.updateData(data)
        return data

class MyStromSwitch(Device):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.com_type = 'http'
        self.actions = {
            'on': {
                'type': 'button',
                'label': 'On'
            },

            'off': {
                'type': 'button',
                'label': 'Off'
            },

            'toggle': {
                'type': 'button',
                'label': 'Toogle'
            },

            'getState': {
                'type': 'button',
                'label': 'Refresh data'
            }
        }

        self.getState()

    def action(self, action, msg=None):
        if action not in self.actions.keys():
            log.error('{} is not allowed ({})'.format(action, str(self.actions.keys())))
            return False, None

        if action == 'on' or action == 'off' or action == 'toggle':
            data = self.setState(action)

        if action == 'getState':
            data = self.getState()

        return data

    def getState(self):
        r = requests.get('http://{}/report'.format(self.address))

        if r.status_code != 200:
            log.error('http request not 200: {} - '.format(str(r.status_code), str(r.text)))
            return None

        data = r.json()
        self.updateData(data)

        return data

    def setState(self, state='Toogle'):
        allowed = [ 'TOGGLE', 'ON', 'OFF' ]

        if state.upper() not in allowed:
            log.error('{} is not allowed ({})'.format(state, str(allowed)))
            return None

        if state.upper() == 'TOGGLE':
            path = '/toggle'

        if state.upper() == 'ON':
            path = '/relay?state=1'

        if state.upper() == 'OFF':
            path = '/relay?state=0'

        url = 'http://{}'.format(self.address) + path
        r = requests.get(url)

        if r.status_code != 200:
            log.error('http request not 200: {} - '.format(str(r.status_code), str(r.text)))
            return None

        _, data = self.getState()

        return data

class LoraLogDevice(Device):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.com_type = 'lora'
        self.rewrite_keys = {
            "TempC_SHT": "temperature",
            "Hum_SHT": "humidity"
        }

    def receiveMsg(self, data):
        if data.get('uplink_message'):
            if data['uplink_message'].get('decoded_payload'):
                for k,v in data['uplink_message']['decoded_payload'].items():
                    data[k] = v
                    if k in self.rewrite_keys.keys():
                        data[self.rewrite_keys[k]] = v

        self.updateData(data)

class ZigBeeDevice(Device):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.com_type = 'zigbee'

        if not self._config.get('zigbee_id', False):
            self.zigbee_id = self.name

        if not self.__dict__.get('zigbee_id'):
            self.zigbee_id = self.name

    def receiveMsg(self, data):
        self.updateData(data)

    def sendMsg(self, msg, topic_suffix='/set'):
        config = Config()
        server = config['zigbee2mqtt']['server']
        topic = config['zigbee2mqtt']['topic'] + '/' + self.zigbee_id + topic_suffix

        client = mqtt.Client()
        client.connect(config['zigbee2mqtt']['server'], config['zigbee2mqtt']['port'], 60)

        sent_msg = client.publish(topic, json.dumps(msg))
        sent_msg.wait_for_publish()

        return True

class ZigBeeLogDevice(ZigBeeDevice):
    def receiveMsg(self, data):
        self.updateData(data)

class ZigBeeActionDevice(ZigBeeDevice):
    def __init__(self, *args, **kwargs):
        self.action = None
        self.action_history = []

        super().__init__(*args, **kwargs)

    def receiveMsg(self, data):
        config = Config()
        self.action = data.get('action', None)

        if not self.action:
            return False

        timestamp = time.time()
        self.action_history.insert(0, { "action": self.action, "timestamp": timestamp })

        if len(self.action_history) > 10:
            self.action_history = self.action_history[:10]

        self.scene = self.scenes.get(self.action)

        if not self.scene:
            log.error("no scene found!")
            return False

        if type(self.scene) == str:
            log.info("calling scene: {}".format(self.scene))
            _p = subprocess.Popen([ sys.executable, "scenes/{}.py".format(self.scene) ])

        if type(self.scene) == list:
            log.info("calling scene: {} with params {}".format(self.scene[0], self.scene[1:]))
            cmd = self.scene
            cmd[0] = "scenes/{}.py".format(self.scene[0])
            cmd.insert(0, sys.executable)

            _p = subprocess.Popen(cmd)

        self.updateData(data)


class Fingerbot(ZigBeeDevice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = {
            'press': {
                'type': 'button',
                'label': 'Press'
            }
        }


    def action(self, action, msg=None):
        if action not in self.actions.keys():
            log.error('{} is not allowed ({})'.format(action, str(self.actions.keys())))
            return False, None

        if action == 'press':
            data = self.press()

        return data

    def press(self):
        # linkquality must be set to work
        msg = { 'linkquality': 109, 'state': 'ON' }

        if not self.sendMsg(msg, '/get'):
            return None

        return msg

class IkeaBaseButton(ZigBeeActionDevice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class IkeaSwitch(ZigBeeDevice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = {
            'on': {
                'type': 'button',
                'label': 'On'
            },

            'off': {
                'type': 'button',
                'label': 'Off'
            },

            'toggle': {
                'type': 'button',
                'label': 'Toogle'
            },

            'getState': {
                'type': 'button',
                'label': 'Refresh data'
            }
        }


    def action(self, action, msg=None):
        if action not in self.actions.keys():
            log.error('{} is not allowed ({})'.format(action, str(self.actions.keys())))
            return False, None

        if action == 'on' or action == 'off' or action == 'toggle':
            data = self.setState(action)

        if action == 'getState':
            data = self.getState()

        return data

    def getState(self):
        msg = { 'state': '' }

        if not self.sendMsg(msg, '/get'):
            return None

        return msg

    def setState(self, state='Toogle'):
        allowed = [ 'TOGGLE', 'ON', 'OFF' ]

        if state.upper() not in allowed:
            log.error('{} is not allowed ({})'.format(state, str(allowed)))
            return None

        msg = { 'state': state.upper() }

        if not self.sendMsg(msg):
            return None

        self.updateData(msg)

        return msg

class IkeaLamp(IkeaSwitch):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = { 
            'on': {
                'type': 'button',
                'label': 'On'
            },

            'off': {
                'type': 'button',
                'label': 'Off'
            },

            'toggle': {
                'type': 'button',
                'label': 'Toogle'
            },

            'brightness': {
                'type': 'slider',
                'min': 1,
                'max': 253,
                'additional_kv': {
                    'transition': 1
                }
            },

            'color_temp': {
                'type': 'slider',
                'min': 250,
                'max': 453,
                'additional_kv': {
                    'transition': 1
                }
            },

            'effect': {
                'type': 'list'
            },

            'getState': {
                'type': 'button',
                'label': 'Refresh data'
            }

            }

    def action(self, action, msg=None):
        if action not in self.actions.keys():
            log.error('{} is not allowed ({})'.format(action, str(self.actions.keys())))
            return False

        if action == 'on' or action == 'off' or action == 'toggle':
            data = self.setState(action)

        if action == 'getState':
            data = self.getState()

        if action == 'brightness':
            if not type(msg) == dict:
                error = 'ERROR - mallformed msg object. msg = { "brightness": 20, "transition": 2 }'
                log.error(error)
                return False, error

            brightness = msg.get('brightness', None)
            transition = msg.get('transition', 1)

            if not brightness:
                error = 'ERROR - mallformed msg object. msg = { "brightness": 20, "transition": 2 }'
                log.error(error)
                return False, error

            data = self.setBrightness(brightness, transition)

        if action == 'color_temp':
            if not type(msg) == dict:
                error = 'ERROR - mallformed msg object. msg = { "color_temp": 20, "transition": 2 }'
                log.error(error)
                return False, error

            color_temp = msg.get('color_temp', None)
            transition = msg.get('transition', 1)

            if not color_temp:
                error = 'ERROR - mallformed msg object. msg = { "color_temp": 20, "transition": 2 }'
                log.error(error)
                return False, error

            data = self.setColorTemp(color_temp, transition)

        if action == 'effect':
            if not type(msg) == dict:
                error = 'ERROR - mallformed msg object. Example: msg = { "effect": "blink" }'
                log.error(error)
                return False, error

            effect = msg.get('effect', None)

            if not effect:
                error = 'ERROR - mallformed msg object. Example: msg = { "effect": "blink" }'
                log.error(error)
                return False, error

            data = self.doEffect(effect)

        return data

    def setBrightness(self, data, transition=1):
        if data not in range(0,254):
            error = 'ERROR - data must be integer between 0 and 253'
            log.error(error)

            return False, error

        if type(transition) != int:
            error = 'ERROR - transition must be an integer.'
            log.error(error)

            return False, error

        msg = { 'brightness': data, 'transition': transition }
        send = self.sendMsg(msg)

        if not send:
            return False

        self.updateData(msg)

        return msg

    def setColorTemp(self, data, transition=1):
        allowed = [ 'coolest', 'cool', 'neutral', 'warm', 'warmest' ]

        if data not in range(250,454) and data not in allowed:
            error = 'ERROR - data must be integer between 250 and 453 or {}'.format(allowed)
            log.error(error)

            return False, error

        if type(transition) != int:
            error = 'ERROR - transition must be an integer.'
            log.error(error)

            return False, error

        self.color_temp = data
        msg = { 'color_temp': self.color_temp, 'transition': transition  }
        send = self.sendMsg(msg)

        if not send:
            return False

        self.updateData(msg)

        return msg

    def doEffect(self, data):
        allowed = [ 'blink', 'breathe', 'okay', 'channel_change', 'finish_effect', 'stop_effect' ]

        if data not in allowed:
            error = 'ERROR - msg must be one of {}'.format(allowed)
            log.error(error)

            return False, error

        msg = { 'effect': data }
        send = self.sendMsg(msg)

        if not send:
            return False

        self.updateData(msg)

        return msg


