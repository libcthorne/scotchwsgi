import logging
import sys
from io import BytesIO

import gevent
import gevent.monkey
import gevent.pool

from scotchwsgi import const
from scotchwsgi.request import WSGIRequest

logger = logging.getLogger(__name__)

class WSGIWorker(object):
    def __init__(self, application, sock, host, port):
        self.application = application
        self.sock = sock
        self.host = host
        self.port = port

    def start(self):
        gevent.monkey.patch_all()
        pool = gevent.pool.Pool(size=const.MAX_CONNECTIONS)

        while True:
            conn, addr = self.sock.accept()
            pool.spawn(self.handle_connection, conn, addr)

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
            'wsgi.multiprocess': True,
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
                writer.write(status.encode(const.STR_ENCODING))
                writer.write(b"\r\n")

                for header_name, header_value in response_headers:
                    writer.write(header_name.encode(const.STR_ENCODING))
                    writer.write(b": ")
                    writer.write(header_value.encode(const.STR_ENCODING))
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
