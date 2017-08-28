#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys

def error_before_write(start_response):
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)

    # simulate an exception here, before headers are written
    status = '500 ERROR'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers, sys.exc_info())

    return [
        b"Something went wrong",
    ]

def error_after_write(start_response):
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)

    def error():
        # simulate an exception here, after headers are written
        raise Exception("something bad happened")

    try:
        yield b"So far so good"
        error()
        yield b"Don't send me"
    except:
        status = '500 ERROR'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers, sys.exc_info())
        return []

def error_app(environ, start_response):
    route = environ['PATH_INFO']
    if route == '/error_before_write':
        return error_before_write(start_response)
    elif route == '/error_after_write':
        return error_after_write(start_response)
    else:
        raise AssertionError("Unknown route %s" % route)

################################################################

from multiprocessing import Process
from wsgiref.validate import validator

import requests

from scotchwsgi.server import WSGIServer

HOST = "localhost"
PORT = 8080
URL = "http://{}:{}".format(HOST, PORT)

def get_request(path):
    return requests.get("{}{}".format(URL, path))

def run_tests():
    r = get_request('/error_before_write')
    print(r)
    assert r.status_code == 500
    assert r.text == "Something went wrong"

    r = get_request('/error_after_write')
    assert r.status_code == 200
    assert "Don't send me" not in r.text

def start_server():
    validator_app = validator(error_app)
    server = WSGIServer(HOST, PORT, validator_app)
    server.start()

if __name__ == '__main__':
    p = Process(target=start_server)
    p.start()
    run_tests()
    p.terminate()
