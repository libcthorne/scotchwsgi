#! /usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

################################################################

from multiprocessing import Process

import requests

from server import WSGIServer

HOST = "localhost"
PORT = 8080
URL = "http://{}:{}".format(HOST, PORT)

def get_request(path):
    return requests.get("{}{}".format(URL, path))

def run_tests():
    r = get_request('/')
    print(r)

def start_server():
    server = WSGIServer(HOST, PORT, app)
    server.start()

if __name__ == '__main__':
    p = Process(target=start_server)
    p.start()
    run_tests()
    p.terminate()
