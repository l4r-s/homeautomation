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

#def auth(f):
#    @wraps(f)
#    def wrapper(*args, **kwargs):
#        token = request.headers.get('Token')
#
#        if token not in config['api_tokens_list']:
#            abort(make_response(jsonify(message="Wrong or unspecified api token!"), 401))
#
#        return f(*args, **kwargs)
#
#    return wrapper
#
#def auth_admin(f):
#    @wraps(f)
#    def wrapper(*args, **kwargs):
#        token = request.headers.get('Token')
#
#        # check token auth
#        if token not in config['api_tokens_list']:
#            abort(make_response(jsonify(message="Wrong or unspecified api token!"), 401))
#
#        # check user is admin
#        for key in config['api_tokens'].keys():
#            if token != config['api_tokens'][key]['token']:
#                continue
#
#            if not config['api_tokens'][key].get('admin', False):
#                abort(make_response(jsonify(message="Action not allowed for this user!"), 401))
#
#        return f(*args, **kwargs)
#
#    return wrapper
#
#def load_file(uuid):
#    filename = config['storage_directory'].rstrip('/') + '/' + uuid + '.json'
#
#    try:
#        with open(filename) as f:
#            data = json.load(f)
#    except:
#        abort(make_response(jsonify(message='not found!'), 404))
#
#    return data
#
#def save_file(data):
#    filename = config['storage_directory'].rstrip('/') + '/' + data['uuid'] + '.json'
#    with open(filename, 'w') as f:
#        json.dump(data, f)
#
#    return
#
#def delete_file(uuid):
#    filename = config['storage_directory'].rstrip('/') + '/' + uuid + '.json'
#    os.remove(filename)
#
#    return

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

#@app.route('/api/login', methods = ['POST'])
#@auth
#def login():
#    return jsonify(ok=True)
#
#@app.route('/api/list', methods = ['GET'])
#@app.route('/api/list/<uuid>', methods = ['GET', 'DELETE'])
#@auth_admin
#def list(uuid=None):
#    if request.method == 'DELETE':
#        if not uuid:
#            abort(make_response(jsonify(message='UUID is required!'), 500))
#
#        delete_file(uuid)
#
#        return jsonify(message='msg with id {} deleted succesfully!'.format(uuid))
#
#    data = []
#    if not uuid:
#        files = os.listdir(config['storage_directory'])
#
#        for f in files:
#            if f.split('.')[-1] != 'json':
#                continue
#
#            data.append(load_file(f.replace('.json','')))
#
#    if uuid:
#        data.append(load_file(uuid))
#
#    return jsonify(data)
#
#@app.route('/api/stats', methods = ['GET'])
#@app.route('/api/stats/<user>', methods = ['GET'])
#@app.route('/api/stats/<user>/<year>', methods = ['GET'])
#@app.route('/api/stats/<user>/<year>/<month>', methods = ['GET'])
#@auth_admin
#def stats(user=None, year=None, month=None):
#    if not user:
#        data = { 'users': [] }
#        data['users'] = os.listdir(config['stats_directory'])
#
#        return jsonify(data)
#
#    if not year:
#        data = { 'years': [] }
#
#        try:
#            data['years'] = os.listdir(config['stats_directory'] + user)
#        except:
#            abort(make_response(jsonify(message='No records found!'), 404))
#
#        return jsonify(data)
#
#    if not month:
#        data = { 'months': [] }
#
#        try:
#            data['months'] = os.listdir(config['stats_directory'] + user + '/' + year)
#        except:
#            abort(make_response(jsonify(message='No records found!'), 404))
#
#        return jsonify(data)
#
#    stats = []
#    stats_dir = config['stats_directory'] + user + '/' + str(year) + '/' + str(month) + '/'
#
#    try:
#        stats_files = os.listdir(stats_dir)
#    except:
#        abort(make_response(jsonify(message='No records found!'), 404))
#
#    for file in stats_files:
#        if file.split('.')[-1] != 'json':
#            continue
#
#        with open(stats_dir + file) as f:
#            data = json.load(f)
#
#        data['date'] = year + '-' + month + '-' + file.replace('.json', '')
#        stats.append(data)
#
#    return jsonify(stats)
#
#@app.route('/api/send', methods = ['POST'])
#@auth
#def send():
#    # Takes format:
#    #    {
#    #        "destination": "destination",
#    #        "text": "hello world",
#    #        "sender": "TestSender",
#    #        "retention": "14days" (optional)
#    #    }
#
#    # validation
#    validation_errors = []
#    data = request.get_json(force=True)
#
#    if not data.get('sender'):
#        data.sender = config['default_sender']
#
#    if len(data.get('sender')) > 11:
#        validation_errors.append('sender must not be longer than 11 characters!')
#
#    if not data.get('retention'):
#            data['retention'] = config['default_retention']
#
#    if not data.get('text'):
#        validation_errors.append('text field is needed!')
#
#    if not data.get('destination'):
#        validation_errors.append('destination field is needed!')
#
#    if type(data.get('retention')) != int:
#        validation_errors.append('retention must be an integer (how many days the message should be stored)!')
#
#    if data.get('destination'):
#        try:
#            temp = phonenumbers.parse(data.get('destination'), None)
#        except:
#            validation_errors.append('destination mobile number format is not valid!')
#
#    if validation_errors:
#        abort(make_response(jsonify(message='validation failed!', errors=validation_errors), 401))
#
#    # get user
#    token = request.headers.get('Token')
#    for key in config['api_tokens'].keys():
#        if token != config['api_tokens'][key]['token']:
#            continue
#
#        data['user'] = key
#
#    data['log'] = []
#    data['requester_ip'] = request.access_route[0]
#    data['state'] = 'waiting'
#    data['created'] = time.time()
#    data['uuid'] = str(uuid.uuid4().hex)
#
#    save_file(data)
#
#    return jsonify(data)
#
#if __name__ == '__main__':
#    app.run(debug=False,host='0.0.0.0')

# vim: set syntax=python:
