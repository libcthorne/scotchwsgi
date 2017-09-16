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
        b"You sent a %s request" % (
            environ['REQUEST_METHOD'].encode('ascii')
        ),
    ]

################################################################

import unittest

import requests

from .base import WSGIAppTestCase

class TestSimpleApp(WSGIAppTestCase):
    APP = simple_app

    def test_simple_get(self):
        r = self.get_request('/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "Hello world!\nYou sent a GET request")

if __name__ == '__main__':
    unittest.main()
