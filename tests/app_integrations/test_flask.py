#! /usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, redirect, request

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/test')
def hello_world_2():
    return 'Hello, World 2!'

@app.route('/params_test')
def params_test():
    argstr = ''
    for arg_name, arg_value in request.args.items():
        argstr += '{}: {}\n'.format(arg_name, arg_value)
    return argstr

@app.route('/post_test', methods=['POST'])
def post_test():
    argstr = ''
    for arg_name, arg_value in request.form.items():
        argstr += '{}: {}\n'.format(arg_name, arg_value)
    return argstr

@app.route('/redirect')
def redirect_test():
    return redirect('/test')

################################################################

import unittest

import requests

from .base import WSGIAppTestCase

class TestFlaskApp(WSGIAppTestCase):
    APP = app

    def test_valid_get_1(self):
        r = self.get_request('/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "Hello, World!")

    def test_valid_get_2(self):
        r = self.get_request('/test')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "Hello, World 2!")

    # def test_valid_get_with_args(self):
    #     r = self.get_request('/params_test?arg1=test1&arg2=test2')
    #     self.assertEqual(r.status_code, 200)
    #     self.assertIn("arg1: test1", r.text)
    #     self.assertIn("arg2: test2", r.text)

    # def test_valid_post(self):
    #     r = self.post_request('/post_test', data=dict(arg1='test1', arg2='test2'))
    #     self.assertEqual(r.status_code, 200)
    #     self.assertIn(r.text, "arg1: test1\narg2: test2\n")

    # def test_redirect(self):
    #     r = self.get_request('/redirect', allow_redirects=False)
    #     self.assertEqual(r.status_code, 302)

if __name__ == '__main__':
    unittest.main()
