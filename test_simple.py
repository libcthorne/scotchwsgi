#! /usr/bin/env python
# -*- coding: utf-8 -*-

# From PEP 3333
def simple_app(environ, start_response):
    """Simplest possible application object"""
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)
    return [
        b"Hello world!\n",
        b"You sent a %s request" % environ['REQUEST_METHOD'],
    ]

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
    assert r.status_code == 200
    assert r.text == "Hello world!\nYou sent a GET request"

def start_server():
    server = WSGIServer(HOST, PORT, simple_app)
    server.start()

if __name__ == '__main__':
    p = Process(target=start_server)
    p.start()
    run_tests()
    p.terminate()
