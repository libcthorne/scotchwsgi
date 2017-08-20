#! /usr/bin/env python
# -*- coding: utf-8 -*-

HOST = "localhost"
PORT = 8080

from server import WSGIServer
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

if __name__ == '__main__':
    server = WSGIServer(HOST, PORT, app)
    server.start()
