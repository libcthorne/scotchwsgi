#! /usr/bin/env python
# -*- coding: utf-8 -*-

import logging

logging.basicConfig(level=logging.INFO)

# From PEP 3333
def app(environ, start_response):
    """Simplest possible application object"""
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)
    return [
        b"Hello world!\n",
        b"You sent a %s request" % (
            environ['REQUEST_METHOD'].encode('ascii'),
        )
    ]

################################################################

HOST = "localhost"
PORT = 8080

from scotchwsgi.server import WSGIServer

if __name__ == '__main__':
    server = WSGIServer(HOST, PORT, __name__)
    server.start()
