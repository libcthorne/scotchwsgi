import unittest

import requests

from .base import WSGIAppTestCase

class TestSimpleApp(WSGIAppTestCase):
    APP = 'simple_app'

    def test_simple_get(self):
        r = self.get_request('/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "Hello world!\nYou sent a GET request")

if __name__ == '__main__':
    unittest.main()
