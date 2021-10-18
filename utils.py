import os
import json
import yaml

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

class Device():
    def __init__(self, name, zigbee_id=None, data=False):
        self.name = name
        self.load()
        self.zigbee_id = zigbee_id

        if data:
            self.__dict__.update(data)

    def load(self):
        config = Config()
        storage_directory = config['storage_directory']
        devices = config['devices']
        filename = storage_directory.rstrip('/') + '/' + self.name + '.json'

        data = {}
        name = self.name

        if os.path.isfile(filename):
            with open(filename) as f:
                data = json.load(f)

        data.update(devices[self.name])

        self.__dict__.update(data)
        self.name = name


    def save(self):
        config = Config()
        storage_directory = config['storage_directory']
        devices = config['devices']
        filename = storage_directory.rstrip('/') + '/' + self.name + '.json'

        with open(filename, 'w') as f:
            json.dump(self.__dict__, f)

        return

class ZigBeeDevice(Device):
    def sendMsg(self, msg):
        if not self.zigbee_id:
            print('ERROR - zigbee_id must be present on object!')
            return False

        config = Config()
        server = config['zigbee2mqtt']['server']
        topic = config['zigbee2mqtt']['topic'] + '/' + self.zigbee_id + '/set'

        print('msg: {}, server: {}, topic: {}'.format(msg, server, topic))
        return True

class IkeaSwitch(ZigBeeDevice):
    def setState(self, state='Toogle'):
        allowed = [ 'TOOGLE', 'ON', 'OFF' ]

        if state.upper() not in allowed:
            print('ERROR - {} is not allowed ({})'.format(state, str(allowed)))
            return False

        msg = { 'state': state.upper() }

        if not self.sendMsg(msg):
            return False

        self.__dict__.update(msg)
        self.save()

        return True, msg

class IkeaLamp(IkeaSwitch):
    def setBrightness(self, data, transition=1):
        if data not in range(0,254):
            print('ERROR - data must be integer between 0 and 254')
            return False

        if type(transition) != int:
            print('ERROR - transition must be an integer.')
            return False

        self.brightness = data
        msg = { 'brightness': self.brightness, 'transition': transition }

        return True, msg

    def setColorTemp(self, data, transition=1):
        allowed = [ 'coolest', 'cool', 'neutral', 'warm', 'warmest' ]

        if data not in range(250,454) and data not in allowed:
            print('ERROR - data must be integer between 250 and 454 or {}'.format(allowed))
            return False

        if type(transition) != int:
            print('ERROR - transition must be an integer.')
            return False

        self.color_temp = data
        msg = { 'color_temp': self.color_temp, 'transition': transition  }

        return True, msg

    def doEffect(self, data):
        allowed = [ 'blink', 'breathe', 'okay', 'channel_change', 'finish_effect', 'stop_effect' ]

        if data not in allowed:
            print('ERROR - data must be one of {}'.format(allowed))
            return False

        msg = { 'effect': data }
        return True, msg

#def delete_file(uuid):
#    filename = config['storage_directory'].rstrip('/') + '/' + uuid + '.json'
#    os.remove(filename)
#
#    return


