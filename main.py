#! /usr/bin/env python
# -*- coding: utf-8 -*-

from server import WSGIServer

HOST = "localhost"
PORT = 8080

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

if __name__ == '__main__':
    server = WSGIServer(HOST, PORT, simple_app)
    server.start()
