import os
import time
import json
import yaml
import uuid
import logging
import tempfile
import requests

from flask import Flask
#from flask import _app_ctx_stack
from flask import abort
from flask import request
from flask import jsonify
from flask import make_response
from flask import send_file
from flask import after_this_request
from flask import send_from_directory
from flask import url_for
from flask import redirect
from flask_cors import CORS
from flask import Response
from flask import stream_with_context
from flask import render_template

from utils import *

##
# init app
##
app = Flask(__name__, template_folder='ui')
app.logger.setLevel(logging.INFO)
CORS(app)

config = Config()
# debug
##
if app.config['DEBUG']:
    app.logger.info(app.config)
    app.logger.info(config)

# never cache
@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'

    return r

##
# routes
##
# ui files
@app.route('/')
def ui_index():
    from_data = request.args.get('from')
    if not from_data:
        from_data = "-1days"

    devices, _ = loadDevices()

    return render_template(
        "index.html",
        devices = devices,
        from_data = from_data,
        device_groups = config['device_groups']
    )

@app.route('/details/<device>')
def ui_details(device):
    metrics = []
    from_data = request.args.get('from')
    if not from_data:
        from_data = "-1days"

    url = "{}/metrics/find?query={}.{}.*".format(
        config['metrics']['render_api_base_url'],
        config['metrics']['prefix'],
        device
    )

    r = requests.get(url, timeout=3)
    #if r.status_code != 200:
    #    data = {
    #        "status": "error",
    #        "data": r.text()
    #    }

    if r.status_code == 200:
        for m in r.json():
            metrics.append(m['text'])

    device_data = loadDevice(device)

    return render_template(
        "details.html",
        device = device,
        metrics = metrics,
        from_data = from_data,
        device_data = device_data
    )

@app.route('/<path:filename>')
def ui(filename=None):
    if filename == None:
        filename = 'index.html'

    return send_from_directory('ui/', filename)

@app.route('/api/v1/devices')
def show_devices():
    data = []
    devices, _ = loadDevices()

    for d in devices.keys():
        data.append(devices[d].__dict__)

    return jsonify(list(devices.keys()))

@app.route('/api/v1/devices/<device>', methods = [ 'GET', 'POST' ])
def show_device(device):
    device = loadDevice(device)
    if not device:
        abort(make_response(jsonify(message='device not found!'), 404))

    if request.method == 'GET':
        return jsonify(device.__dict__)

    if request.method == 'POST':
        data = request.get_json(force=True)
        print(data)
        action = data.get('action')
        msg = data.get('msg', {})

        # try to make msg an integer
        try:
            msg = int(msg)
        except:
            pass

        if not action:
            abort(make_response(jsonify(message='malformed payload'), 400))

        if action not in device.actions:
            abort(make_response(
                jsonify(
                    message = 'action not allowed',
                    actions = device.actions
                ), 400)
            )

        return jsonify(device.action(action, msg))

@app.route('/api/v1/devices/<device>/metrics', methods = [ 'GET' ])
def device_metrics(device):
    url = "{}/metrics/find?query={}.{}.*".format(
        config['metrics']['render_api_base_url'],
        config['metrics']['prefix'],
        device
    )

    r = requests.get(url, timeout=3)
    if r.status_code != 200:
        data = {
            "status": "error",
            "data": r.text()
        }

    if r.status_code == 200:
        data = []

        for m in r.json():
            data.append(m['text'])

    return jsonify(data)

@app.route('/api/v1/device_groups/<device_group_name>/metrics/<metric>', methods = [ 'GET' ])
def device_group_metrics_render(device_group_name, metric):
    from_data = request.args.get('from')

    if not from_data:
        from_data = "-1days"

    device_group = config['device_groups'][device_group_name]
    device_list = ','.join(device_group['devices'])

    url = "%s/render/?target=aliasByNode(cactiStyle(aliasByNode(%s.{%s}.%s,1)),3)&from=%s&height=400&width=800&title=%s&bgcolor=white&fgcolor=black&drawNullAsZero=false&lineMode=connected&colorList=green,blue,yellow,black,purple,orange,red,darkgrey,rose,magenta&yMin=0"%(
        config['metrics']['render_api_base_url'],
        config['metrics']['prefix'],
        device_list,
        metric,
        from_data,
        metric
    )

    r = requests.get(url, stream = True)
    return Response(stream_with_context(r.iter_content()), content_type = r.headers['content-type'])

@app.route('/api/v1/devices/<device>/metrics/<metric>', methods = [ 'GET' ])
def device_metrics_render(device, metric):
    from_data = request.args.get('from')

    if not from_data:
        from_data = "-1days"

    url = "{}/render/?target=aliasByNode(cactiStyle(aliasByNode({}.{}.{},-1)),1)&from={}&height=400&width=800&title={}&bgcolor=white&fgcolor=black&drawNullAsZero=false&lineMode=connected&colorList=green&yMin=0".format(
        config['metrics']['render_api_base_url'],
        config['metrics']['prefix'],
        device,
        metric,
        from_data,
        metric
    )

    r = requests.get(url, stream = True)
    return Response(stream_with_context(r.iter_content()), content_type = r.headers['content-type'])


# vim: set syntax=python:
