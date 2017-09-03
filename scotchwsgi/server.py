import functools
import logging
import socket
import ssl
import sys
from io import BytesIO

import gevent
import gevent.monkey
import gevent.pool

MAX_CONNECTIONS = 1000
STR_ENCODING = 'latin-1'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WSGIRequest(object):
    def __init__(self, method, path, query, http_version, headers, body):
        self.method = method
        self.path = path
        self.query = query
        self.http_version = http_version
        self.headers = headers
        self.body = body

    @staticmethod
    def read_request_line(reader):
        request_line = reader.readline().decode(STR_ENCODING)
        logger.info("Received request %s", request_line)

        if request_line:
            request_method, request_uri, http_version = request_line.split(' ', 3)
            request_uri_split = request_uri.split('?', 1)
            request_path = request_uri_split[0]
            if len(request_uri_split) > 1:
                request_query = request_uri_split[1]
            else:
                request_query = ''
        else:
            request_method = ''
            request_path = ''
            request_query = ''
            http_version = ''

        return request_method, request_path, request_query, http_version

    @staticmethod
    def read_headers(reader):
        headers = {}
        while True:
            header = reader.readline().decode(STR_ENCODING).replace('\r\n', '\n').rstrip('\n')
            if header == '':
                break

            header_name, header_value = header.split(':', 1)
            header_name = header_name.lower()
            header_value = header_value.lstrip()
            headers[header_name] = header_value

        logger.debug("Headers: %s", headers)

        return headers

    @staticmethod
    def read_body(reader, content_length):
        if content_length > 0:
            logger.debug("Reading body")
            message_body = reader.read(content_length)
            logger.debug("Body: %s", message_body)
        else:
            logger.debug("No body")
            message_body = b""

        return message_body

    @staticmethod
    def from_reader(reader):
        method, path, query, http_version = WSGIRequest.read_request_line(
            reader
        )

        headers = WSGIRequest.read_headers(
            reader
        )

        body = WSGIRequest.read_body(
            reader,
            int(headers.get('content-length', 0))
        )

        return WSGIRequest(
            method=method,
            path=path,
            query=query,
            http_version=http_version,
            headers=headers,
            body=body,
        )

class WSGIServer(object):
    def __init__(self, host, port, application, ssl_config=None, backlog=None):
        self.host = host
        self.port = port
        self.application = application
        self.ssl_config = ssl_config
        self.backlog = backlog

    def _get_environ(self, request):
        environ = {
            'REQUEST_METHOD': request.method,
            'SCRIPT_NAME': '',
            'SERVER_NAME': self.host,
            'SERVER_PORT': str(self.port),
            'SERVER_PROTOCOL': request.http_version,
            'PATH_INFO': request.path,
            'QUERY_STRING': request.query,
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'wsgi.input': BytesIO(request.body),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': True,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
        }

        environ['PATH_INFO'] = request.path
        environ['QUERY_STRING'] = request.query if request.query else ''

        environ_headers = request.headers.copy()
        if 'content-type' in request.headers:
            environ['CONTENT_TYPE'] = environ_headers.pop('content-type')
        if 'content-length' in request.headers:
            environ['CONTENT_LENGTH'] = environ_headers.pop('content-length')
        for http_header_name, http_header_value in environ_headers.items():
            http_header_name = 'HTTP_{}'.format(http_header_name.upper().replace('-', '_'))
            environ[http_header_name] = http_header_value
        environ_headers.clear()

        return environ

    def _send_response(self, request, writer):
        environ = self._get_environ(request)

        headers_to_send = []
        headers_sent = []

        def write(data):
            if not headers_to_send and not headers_sent:
                raise AssertionError("write() before start_response()")

            elif not headers_sent:
                status, response_headers = headers_to_send[:]
                logger.debug("Send headers %s %s", status, response_headers)

                writer.write(b"HTTP/1.0 ")
                writer.write(status.encode(STR_ENCODING))
                writer.write(b"\r\n")

                for header_name, header_value in response_headers:
                    writer.write(header_name.encode(STR_ENCODING))
                    writer.write(b": ")
                    writer.write(header_value.encode(STR_ENCODING))
                    writer.write(b"\r\n")

                writer.write(b"\r\n")

                headers_sent[:] = [status, response_headers]
                headers_to_send[:] = []

            writer.write(data)
            writer.flush()

        def start_response(status, response_headers, exc_info=None):
            logger.debug("start_response %s %s %s", status, response_headers, exc_info)

            if exc_info:
                try:
                    if headers_sent:
                        logger.debug("Reraising application exception")
                        # reraise original exception if headers already sent
                        raise exc_info[1].with_traceback(exc_info[2])
                finally:
                    exc_info = None # avoid dangling circular ref
            elif headers_sent:
                raise AssertionError("Headers already set")

            headers_to_send[:] = [status, response_headers]

            return write

        logger.debug("Calling into application")
        response_iter = self.application(environ, start_response)

        try:
            for response in response_iter:
                logger.debug("Write %s", response)
                write(response)
        except Exception as e:
            logger.error("Application aborted: %r", e)
        finally:
            response_iter_close = getattr(response_iter, 'close', None)
            if callable(response_iter_close):
                response_iter.close()
            logger.debug("Called into application")

    def handle_connection(self, conn, addr):
        logger.info("New connection: %s", addr)

        reader = conn.makefile('rb')
        writer = conn.makefile('wb')

        request = WSGIRequest.from_reader(reader)
        self._send_response(request, writer)

        logger.debug("Closing connection")

        try:
            reader.close()
        except IOError:
            pass

        try:
            writer.close()
        except IOError:
            pass

        conn.close()

    def start(self):
        gevent.monkey.patch_all()

        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        if self.ssl_config:
            logger.info("Using SSL")
            sock = ssl.wrap_socket(
                sock,
                server_side=True,
                **self.ssl_config,
            )

        if self.backlog:
            sock.listen(self.backlog)
        else:
            sock.listen()

        logger.info("Listening on %s:%d", self.host, self.port)

        pool = gevent.pool.Pool(size=MAX_CONNECTIONS)

        while True:
            conn, addr = sock.accept()
            pool.spawn(self.handle_connection, conn, addr)

def make_server(*args, **kwargs):
    return WSGIServer(*args, **kwargs)
