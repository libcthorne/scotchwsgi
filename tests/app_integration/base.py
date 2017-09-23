import logging
import time
import unittest
from multiprocessing import Process

import requests

from scotchwsgi.server import WSGIServer

logging.basicConfig(level=logging.INFO)

REQUEST_TIMEOUT = 3

class WSGIAppTestCase(unittest.TestCase):
    HOST = "localhost"
    PORT = 8080
    URL = "http://{}:{}".format(HOST, PORT)

    def setUp(self):
        self.server_process = Process(target=self.start_server)
        self.server_process.start()
        while not self.server_process.is_alive():
            # wait for parent process to be started
            time.sleep(0.1)

    def tearDown(self):
        self.server_process.terminate()
        self.server_process.join() # block until terminated

    def start_server(self):
        server = WSGIServer(
            self.HOST, self.PORT,
            "tests.app_integration.{}".format(self.__class__.APP)
        )
        server.start()

    def get_request(self, path, *args, **kwargs):
        return requests.get("{}{}".format(self.URL, path), *args, timeout=REQUEST_TIMEOUT, **kwargs)

    def post_request(self, path, data, *args, **kwargs):
        return requests.post("{}{}".format(self.URL, path), *args, data=data, timeout=REQUEST_TIMEOUT, **kwargs)

