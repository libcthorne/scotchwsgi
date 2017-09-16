import logging
import unittest
from multiprocessing import Process
from wsgiref.validate import validator

import requests

from scotchwsgi.server import WSGIServer

logging.basicConfig(level=logging.INFO)

class WSGIAppTestCase(unittest.TestCase):
    HOST = "localhost"
    PORT = 8080
    URL = "http://{}:{}".format(HOST, PORT)

    def setUp(self):
        self.server_process = Process(target=self.start_server)
        self.server_process.start()

    def tearDown(self):
        self.server_process.terminate()
        self.server_process.join() # block until terminated

    def start_server(self):
        validator_app = validator(self.__class__.APP)
        server = WSGIServer(self.HOST, self.PORT, validator_app)
        server.start()

    def get_request(self, path, *args, **kwargs):
        return requests.get("{}{}".format(self.URL, path), *args, **kwargs)

    def post_request(self, path, data, *args, **kwargs):
        return requests.post("{}{}".format(self.URL, path), *args, data=data, **kwargs)

