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
    except:
        status = '500 ERROR'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers, sys.exc_info())
        yield b"Don't send me"

def error_app(environ, start_response):
    route = environ['PATH_INFO']
    if route == '/error_before_write':
        return error_before_write(start_response)
    elif route == '/error_after_write':
        return error_after_write(start_response)
    else:
        raise AssertionError("Unknown route %s" % route)

################################################################

import unittest

import requests

from .base import WSGIAppTestCase

class TestErrorApp(WSGIAppTestCase):
    APP = error_app

    def test_error_before_write(self):
        r = self.get_request('/error_before_write')
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.text, "Something went wrong")

    def test_error_after_write(self):
        r = self.get_request('/error_after_write')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Don't send me", r.text)

if __name__ == '__main__':
    unittest.main()
