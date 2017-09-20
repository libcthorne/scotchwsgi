import os
import unittest
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

from scotchwsgi.request import WSGIRequest
from scotchwsgi.worker import WSGIWorker

TEST_HOST = 'localhost'
TEST_PORT = 0

def dummy_worker(sock, app):
    return WSGIWorker(
        app,
        sock,
        TEST_HOST,
        os.getpid(),
    )

class TestWorkerEnviron(unittest.TestCase):
    """A worker should return correct environ values"""

    def setUp(self):
        self.hostname = TEST_HOST
        self.port = 5000

        mock_sock = Mock()
        mock_sock.getsockname.return_value = (self.hostname, self.port)
        mock_app = Mock()
        self.worker = dummy_worker(mock_sock, mock_app)

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
        self.assertEqual(environ['SERVER_NAME'], self.hostname)
        self.assertEqual(environ['SERVER_PORT'], str(self.port))
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

class TestWorkerRequestHandling(unittest.TestCase):
    """A worker should only respond to valid requests"""

    def _mock_makefile(self, request_bytes):
        def mock_makefile(mode):
            if mode == 'rb':
                return BytesIO(request_bytes)
            else:
                return Mock()

        return mock_makefile

    def test_valid_request(self):
        mock_app = Mock()
        mock_sock = Mock(getsockname=lambda: (TEST_HOST, TEST_PORT))
        worker = WSGIWorker(mock_app, mock_sock, TEST_HOST, os.getppid())

        mock_conn = Mock(makefile = self._mock_makefile(b"GET / HTTP/1.1\r\n\r\n"))
        mock_addr = Mock()
        with patch('scotchwsgi.worker.WSGIWorker._send_response') as mock_send_response:
            worker._handle_connection(mock_conn, mock_addr)
            mock_send_response.assert_called_once()

    def test_invalid_request(self):
        mock_app = Mock()
        mock_sock = Mock(getsockname=lambda: (TEST_HOST, TEST_PORT))
        worker = WSGIWorker(mock_app, mock_sock, TEST_HOST, os.getppid())

        mock_conn = Mock(makefile = self._mock_makefile(b"junk\r\n"))
        mock_addr = Mock()
        with patch('scotchwsgi.worker.WSGIWorker._send_response') as mock_send_response:
            worker._handle_connection(mock_conn, mock_addr)
            mock_send_response.assert_not_called()

class TestWorkerClosesIterable(unittest.TestCase):
    """
    PEP 3333: If the iterable returned by the application has a
    ``close()`` method, the server or gateway **must** call that
    method upon completion of the current request, whether the request
    was completed normally, or terminated early due to an application
    error during iteration or an early disconnect of the browser.
    """

    def test_normal_termination_iterable_closed(self):
        mock_sock = Mock()
        mock_sock.getsockname.return_value = (TEST_HOST, 5000)

        def normal_iter(self):
            yield b'a'

        iter_mock = MagicMock()
        iter_mock.__iter__ = normal_iter

        mock_app = Mock()
        mock_app.return_value = iter_mock

        request_mock = Mock()
        request_mock.body = b''
        request_mock.headers = {}

        writer_mock = Mock()

        with patch('scotchwsgi.worker.WSGIResponseWriter', return_value=Mock()):
            worker = dummy_worker(mock_sock, mock_app)
            worker._send_response(request_mock, writer_mock)

        iter_mock.close.assert_called_once()

    def test_exception_termination_iterable_closed(self):
        mock_sock = Mock()
        mock_sock.getsockname.return_value = (TEST_HOST, 5000)

        def exception_iter(self):
            yield b'a'
            raise Exception("Iterator exception")

        iter_mock = MagicMock()
        iter_mock.__iter__ = exception_iter

        mock_app = Mock()
        mock_app.return_value = iter_mock

        request_mock = Mock()
        request_mock.body = b''
        request_mock.headers = {}

        writer_mock = Mock()

        with patch('scotchwsgi.worker.WSGIResponseWriter', return_value=Mock()):
            worker = dummy_worker(mock_sock, mock_app)
            worker._send_response(request_mock, writer_mock)

        iter_mock.close.assert_called_once()
