import unittest

import requests

from .base import WSGIAppTestCase

class TestFlaskApp(WSGIAppTestCase):
    APP = 'flask_app'

    def test_valid_get_1(self):
        r = self.get_request('/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "Hello, World!")

    def test_valid_get_2(self):
        r = self.get_request('/test')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "Hello, World 2!")

    def test_valid_get_with_args(self):
        r = self.get_request('/params_test?arg1=test1&arg2=test2')
        self.assertEqual(r.status_code, 200)
        self.assertIn("arg1: test1", r.text)
        self.assertIn("arg2: test2", r.text)

    def test_valid_post(self):
        r = self.post_request('/post_test', data=dict(arg1='test1', arg2='test2'))
        self.assertEqual(r.status_code, 200)
        self.assertIn(r.text, "arg1: test1\narg2: test2\n")

    def test_redirect(self):
        r = self.get_request('/redirect', allow_redirects=False)
        self.assertEqual(r.status_code, 302)

if __name__ == '__main__':
    unittest.main()
