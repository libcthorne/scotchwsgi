import multiprocessing
import os
import time
import unittest
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

import psutil
from gevent import socket

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
    start_response('200 OK', [('Content-Length', '11')])
    return [b'Hello', b' ', b'World']

def dummy_worker(sock, app):
    return WSGIWorker(
        app,
        sock,
        TEST_HOST,
        os.getpid(),
    )

def start_worker_process(sock, app=dummy_app, worker_pid=None, join=False):
    worker = dummy_worker(sock, app)

    worker_process = multiprocessing.Process(target=worker.start)
    worker_process.start()

    if worker_pid:
        worker_pid.value = worker_process.pid

    if join:
        worker_process.join()

    return worker_process

class TestWorkerParentBinding(unittest.TestCase):
    def setUp(self):
        self.sock = open_test_socket()

        self.worker_pid = multiprocessing.Value('i')

        self.parent_process = multiprocessing.Process(
            target=start_worker_process,
            args=(self.sock, dummy_app, self.worker_pid, True)
        )
        self.parent_process.start()

        while self.worker_pid.value == 0 and self.parent_process.is_alive():
            # wait for worker process to be started
            time.sleep(0.1)

    def tearDown(self):
        if self.parent_process.is_alive():
            self.parent_process.terminate()
            self.parent_process.join() # wait for termination
        self.sock.close()

    def test_worker_dies_when_parent_dies(self):
        self.assertTrue(psutil.pid_exists(self.worker_pid.value))
        self.parent_process.terminate()
        self.parent_process.join()
        time.sleep(1)
        self.assertFalse(psutil.pid_exists(self.worker_pid.value))

class TestWorkerEnviron(unittest.TestCase):
    def setUp(self):
        app_mock = Mock()
        self.sock = open_test_socket()
        self.worker = dummy_worker(self.sock, app_mock)

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

class TestWorkerResponse(unittest.TestCase):
    def setUp(self):
        self.sock = open_test_socket()
        self.worker = start_worker_process(self.sock)
        self.client_sock = socket.create_connection((TEST_HOST, TEST_PORT))
        self.reader = self.client_sock.makefile('rb')

    def tearDown(self):
        self.reader.close()
        self.client_sock.close()
        if self.worker.is_alive():
           self.worker.terminate()
           self.worker.join() # wait for termination
        self.sock.close()

    def test_valid_request(self):
        self.client_sock.send(b'GET / HTTP/1.1\r\n\r\n')

        status_line = self.reader.readline()
        self.assertEqual(status_line, b'HTTP/1.1 200 OK\r\n')

        headers = {}
        header = self.reader.readline()
        while header != b'\r\n':
            header_name, header_value = header.split(b': ')
            headers[header_name.lower()] = header_value.rstrip().lower()
            header = self.reader.readline()

        self.assertIn(b'content-length', headers)
        body = self.reader.read(int(headers[b'content-length']))
        self.assertEqual(body, b'Hello World')

    def test_invalid_request(self):
        self.client_sock.send(b'junk\r\n')
        response = self.reader.readline()
        self.assertEqual(response, b'')

class TestWorkerClosesIterable(unittest.TestCase):
    """
    PEP 3333: If the iterable returned by the application has a
    ``close()`` method, the server or gateway **must** call that
    method upon completion of the current request, whether the request
    was completed normally, or terminated early due to an application
    error during iteration or an early disconnect of the browser.
    """
    def test_normal_termination_iterable_closed(self):
        sock_mock = Mock()
        sock_mock.getsockname.return_value = (TEST_HOST, TEST_PORT)

        def normal_iter(self):
            yield b'a'

        iter_mock = MagicMock()
        iter_mock.__iter__ = normal_iter

        app_mock = Mock()
        app_mock.return_value = iter_mock

        request_mock = Mock()
        request_mock.body = b''
        request_mock.headers = {}

        writer_mock = Mock()

        with patch('scotchwsgi.worker.WSGIResponseWriter', return_value=Mock()):
            worker = dummy_worker(sock_mock, app_mock)
            worker._send_response(request_mock, writer_mock)

        iter_mock.close.assert_called_once()

    def test_exception_termination_iterable_closed(self):
        sock_mock = Mock()
        sock_mock.getsockname.return_value = (TEST_HOST, TEST_PORT)

        def exception_iter(self):
            yield b'a'
            raise Exception("Iterator exception")

        iter_mock = MagicMock()
        iter_mock.__iter__ = exception_iter

        app_mock = Mock()
        app_mock.return_value = iter_mock

        request_mock = Mock()
        request_mock.body = b''
        request_mock.headers = {}

        writer_mock = Mock()

        with patch('scotchwsgi.worker.WSGIResponseWriter', return_value=Mock()):
            worker = dummy_worker(sock_mock, app_mock)
            worker._send_response(request_mock, writer_mock)

        iter_mock.close.assert_called_once()
