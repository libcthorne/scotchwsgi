import unittest

import requests

from .base import WSGIAppTestCase
from .error_app import app

class TestErrorApp(WSGIAppTestCase):
    APP = app

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
