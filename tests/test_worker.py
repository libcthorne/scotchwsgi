import multiprocessing
import os
import socket
import time
import unittest

import psutil

from scotchwsgi.request import WSGIRequest
from scotchwsgi.worker import WSGIWorker

TEST_HOST = 'localhost'
TEST_PORT = 9000

def open_test_socket():
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((TEST_HOST, TEST_PORT))
    sock.listen()
    return sock

def dummy_app(environ, start_response):
    start_response('200 OK', [])
    return []

def dummy_worker(sock):
    return WSGIWorker(
        dummy_app,
        sock,
        TEST_HOST,
        os.getpid(),
    )

def start_worker(sock, worker_pid):
    worker = dummy_worker(sock)

    worker_process = multiprocessing.Process(target=worker.start)
    worker_process.start()
    worker_pid.value = worker_process.pid
    worker_process.join()

class TestWorkerParentBinding(unittest.TestCase):
    def setUp(self):
        self.sock = open_test_socket()

        self.worker_pid = multiprocessing.Value('i')

        self.parent_process = multiprocessing.Process(
            target=start_worker,
            args=(self.sock, self.worker_pid)
        )
        self.parent_process.start()

        while self.worker_pid.value == 0 and self.parent_process.is_alive():
            # wait for worker process to be started
            time.sleep(0.1)

    def tearDown(self):
        if self.parent_process.is_alive():
            self.parent_process.terminate()
        self.sock.close()

    def test_worker_dies_when_parent_dies(self):
        self.assertTrue(psutil.pid_exists(self.worker_pid.value))
        self.parent_process.terminate()
        time.sleep(1)
        self.assertFalse(psutil.pid_exists(self.worker_pid.value))

class TestWorkerEnviron(unittest.TestCase):
    def setUp(self):
        self.sock = open_test_socket()
        self.worker = dummy_worker(self.sock)

    def tearDown(self):
        self.sock.close()

    def test_environ_values(self):
        request = WSGIRequest(
            'GET',
            '/path',
            'a=1&b=2',
            'HTTP/1.1',
            {
                'content-type': 'text',
                'content-length': 10,
                'other-header': 'Value',
            },
            b'abc',
        )

        environ = self.worker._get_environ(request)

        # CGI variables
        self.assertEqual(environ['REQUEST_METHOD'], 'GET')
        self.assertEqual(environ['SCRIPT_NAME'], '')
        self.assertEqual(environ['PATH_INFO'], '/path')
        self.assertEqual(environ['QUERY_STRING'], 'a=1&b=2')
        self.assertEqual(environ['CONTENT_TYPE'], 'text')
        self.assertEqual(environ['CONTENT_LENGTH'], 10)
        self.assertEqual(environ['SERVER_NAME'], TEST_HOST)
        self.assertEqual(environ['SERVER_PORT'], str(TEST_PORT))
        self.assertEqual(environ['SERVER_PROTOCOL'], 'HTTP/1.1')
        self.assertEqual(environ['HTTP_OTHER_HEADER'], 'Value')

        # WSGI variables
        self.assertEqual(environ['wsgi.version'], (1, 0))
        self.assertEqual(environ['wsgi.url_scheme'], 'http')
        self.assertEqual(environ['wsgi.input'].readline(), b'abc')
        self.assertIn('wsgi.errors', environ)
        self.assertTrue(environ['wsgi.multithread'])
        self.assertTrue(environ['wsgi.multiprocess'])
        self.assertFalse(environ['wsgi.run_once'])
