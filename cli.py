#!/usr/bin/python3
import argparse
import requests
import os
import sys
import json
import datetime
from tabulate import tabulate

##
# argparse helper for using env variables
##
class EnvDefault(argparse.Action):
    def __init__(self, envvar, required=True, default=None, **kwargs):
        if not default and envvar:
            if envvar in os.environ:
                default = os.environ[envvar]

            if required and default:
                required = False

            super(EnvDefault, self).__init__(default=default, required=required, **kwargs)


    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)

def env_default(envvar):
    def wrapper(**kwargs):
        return EnvDefault(envvar, **kwargs)
    return wrapper

##
# list devices
##
def list_devices(base_url, print_json=False, internal=False):
    url = base_url.rstrip('/') + '/api/v1/devices'
    r = requests.get(url)

    if r.status_code == 200:
        data = r.json()

        if internal:
            return data


        if print_json:
            print(json.dumps(data, indent=2))

        if not print_json:
            # get device details
            new_data = []
            for device in data:
                d = get_device_details(base_url, device, print_json=print_json, internal=True)

                if d:
                    new_data.append(d)

            #print(tabulate([ new_data ], headers="keys"))
            print(tabulate(new_data, headers="keys"))

##
# filter keys for allowed_keys list
##
def filter_keys(data, allowed_keys, prefix=False):
    new_data = {}

    for k,v in data.items():
        if type(v) == dict:
            new_data.update(filter_keys(v, allowed_keys, prefix=k))

        if type(v) != dict:
            if prefix:
                k = str(prefix) + '.' + k

            if k in allowed_keys:
                new_data[k] = v

    return new_data

##
# get device
##
def get_device_details(base_url, device, print_json=None, internal=False):
    # define key for table here per device type:
    keys_overview_per_device = {
        'ikea_lamp':     [ 'battery', 'name', 'state', 'last_update.human' ],
        'ikea_switch':   [ 'battery', 'name', 'state', 'last_update.human' ],
        'ikea_button':   [ 'battery', 'name', 'state', 'last_update.human' ],
        'zigbee_log':     [ 'battery', 'name', 'humidity', 'pressure', 'temperature', 'last_update.human' ],
        'mystrom_switch':[ 'name', 'relay', 'power', 'last_update.human' ],
        'sonos':[ 'name', 'play_state', 'volume', 'last_update.human' ],
    }

    url = base_url.rstrip('/') + '/api/v1/devices/' + device

    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()

        # clean data if if not --json
        # if internal ot not does not matter for this part
        if not print_json:
            allowed_keys = keys_overview_per_device.get(data['type'], [])
            data = filter_keys(data, allowed_keys)

        if internal:
            return data

        if print_json:
            print(json.dumps(data, indent=2))

        if not print_json:
            print(tabulate([ data ], headers="keys"))

def main():
    parser = argparse.ArgumentParser(description="Homeautiomation CLI")
    parser.add_argument('-u', '--url', required=True, action=env_default('HOMEAUTO_URL'), help='Homeautiomation server URL can be set with environment variable HOMEAUTO_URL (format: https://homeautomation.tld)')

    parser.add_argument('-j', '--json', default=False, action='store_true', help='Displays output as json')

    parser.add_argument('-l', '--list', default=False, action='store_true', help='List devices')
    parser.add_argument('-d', '--device', required=False, help='Device for detail view or action')
    parser.add_argument('-a', '--action', required=False, help='Action for the given device (not yet working)')
    args = parser.parse_args()

    if not args.list:
        if not args.device:
            parser.error('-l/--list or -d/--device is required!')

        if args.device:
            get_device_details(args.url, args.device, args.json)

    if args.list:
        list_devices(args.url, args.json)

if __name__ == "__main__":
    main()

