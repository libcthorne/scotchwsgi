import os
import unittest
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

from scotchwsgi.request import WSGIRequest
from scotchwsgi.worker import WSGIWorker

TEST_HOST = 'localhost'
TEST_PORT = 0

def stub_worker(app=None):
    if app is None:
        app = Mock()

    mock_sock = Mock(getsockname=lambda: (TEST_HOST, TEST_PORT))

    mock_import_module = patch('scotchwsgi.worker.importlib.import_module', Mock(return_value=Mock(app=app)))
    mock_import_module.start()
    worker = WSGIWorker('.', mock_sock, TEST_HOST, os.getpid())
    mock_import_module.stop()

    return worker

class TestWorkerEnviron(unittest.TestCase):
    """A worker should return correct environ values"""

    def setUp(self):
        self.hostname = TEST_HOST
        self.port = TEST_PORT
        self.worker = stub_worker()

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
        mock_conn = Mock(makefile = self._mock_makefile(b"GET / HTTP/1.1\r\n\r\n"))
        mock_addr = Mock()

        with patch('scotchwsgi.worker.WSGIWorker._send_response') as mock_send_response:
            worker = stub_worker()
            worker._handle_connection(mock_conn, mock_addr)
            mock_send_response.assert_called_once()

    def test_invalid_request(self):
        mock_conn = Mock(makefile = self._mock_makefile(b"junk\r\n"))
        mock_addr = Mock()

        with patch('scotchwsgi.worker.WSGIWorker._send_response') as mock_send_response:
            worker = stub_worker()
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
        def normal_iter(self):
            yield b'a'

        mock_iter = MagicMock(__iter__=normal_iter)
        mock_app = Mock(return_value=mock_iter)
        mock_request = Mock(body=b'', headers={})
        mock_writer = Mock()

        with patch('scotchwsgi.worker.WSGIResponseWriter', return_value=Mock()):
            worker = stub_worker(mock_app)
            worker._send_response(mock_request, mock_writer)

        mock_iter.close.assert_called_once()

    def test_exception_termination_iterable_closed(self):
        def exception_iter(self):
            yield b'a'
            raise Exception("Iterator exception")

        mock_iter = MagicMock(__iter__=exception_iter)
        mock_app = Mock(return_value=mock_iter)
        mock_request = Mock(body=b'', headers={})
        mock_writer = Mock()

        with patch('scotchwsgi.worker.WSGIResponseWriter', return_value=Mock()):
            worker = stub_worker(mock_app)
            worker._send_response(mock_request, mock_writer)

        mock_iter.close.assert_called_once()
