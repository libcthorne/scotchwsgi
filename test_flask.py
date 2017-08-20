#! /usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, redirect, request
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/test')
def hello_world_2():
    return 'Hello, World 2!'

@app.route('/params_test')
def params_test():
    argstr = ''
    for arg_name, arg_value in request.args.items():
        argstr += '{}: {}\n'.format(arg_name, arg_value)
    return argstr

@app.route('/post_test', methods=['POST'])
def post_test():
    argstr = ''
    for arg_name, arg_value in request.form.items():
        argstr += '{}: {}\n'.format(arg_name, arg_value)
    return argstr

@app.route('/redirect')
def redirect_test():
    return redirect('/test')

################################################################

from multiprocessing import Process

import requests

from server import WSGIServer

HOST = "localhost"
PORT = 8080
URL = "http://{}:{}".format(HOST, PORT)

def get_request(path):
    return requests.get("{}{}".format(URL, path))

def post_request(path, data):
    return requests.post("{}{}".format(URL, path), data=data)

def run_tests():
    r = get_request('/')
    print(r)
    assert r.status_code == 200
    assert r.text == "Hello, World!"

    r = get_request('/test')
    print(r)
    assert r.status_code == 200
    assert r.text == "Hello, World 2!"

    r = get_request('/params_test?arg1=test1&arg2=test2')
    print(r)
    assert r.status_code == 200
    assert r.text == "arg1: test1\narg2: test2\n"

    r = post_request('/post_test', data=dict(arg1='test1', arg2='test2'))
    print(r)
    assert r.status_code == 200
    assert r.text == "arg1: test1\narg2: test2\n"

    r = get_request('/redirect')
    print(r)
    assert r.status_code == 302

def start_server():
    server = WSGIServer(HOST, PORT, app)
    server.start()

if __name__ == '__main__':
    p = Process(target=start_server)
    p.start()
    run_tests()
    p.terminate()
