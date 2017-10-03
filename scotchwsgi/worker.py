import importlib
import logging
import os
import signal
import sys
import time
from io import BytesIO

import gevent
import gevent.monkey
import gevent.pool
import gevent.server

from scotchwsgi import const
from scotchwsgi.response import WSGIResponseWriter
from scotchwsgi.request import WSGIRequest

logger = logging.getLogger(__name__)

class WSGIWorker(object):
    def __init__(self, app_location, sock, hostname, parent_pid, request_timeout):
        gevent.monkey.patch_all()

        # Ignore interrupts to disable KeyboardInterrupt being logged
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        # Allow app location to refer to files in cwd
        sys.path.append(os.getcwd())

        self.sock = sock
        self.hostname = hostname
        _, self.port = sock.getsockname()
        self.parent_pid = parent_pid
        self.request_timeout = request_timeout

        app_module = importlib.import_module(app_location)
        if not hasattr(app_module, 'app'):
            logger.error("'app' not found in {}".format(app_location))
            sys.exit(1)

        self.application = app_module.app

    def start(self):
        logger.info("Worker starting (PID: %d)", os.getpid())

        pool = gevent.pool.Pool(size=const.MAX_CONNECTIONS)

        server = gevent.server.StreamServer(
            self.sock,
            self._handle_connection,
            spawn=pool,
        )
        server.start()

        while True:
            if os.getppid() != self.parent_pid:
                logger.info("Worker parent changed, exiting")
                break
            time.sleep(1)

    def _handle_connection(self, conn, addr):
        logger.info("New connection: %s", addr)

        reader = conn.makefile('rb')
        writer = conn.makefile('wb')
        close_connection = False

        while not close_connection:
            try:
                with gevent.Timeout(self.request_timeout):
                    request = WSGIRequest.from_reader(reader)
            except ValueError:
                logger.error("Invalid request received from: %s", addr)
                self._send_error("400 Bad Request", writer)
                close_connection = True
            except NotImplementedError:
                logger.error("Unsupported request received from: %s", addr)
                self._send_error("501 Not Implemented", writer)
                close_connection = True
            except gevent.Timeout:
                logger.info("Connection timed out: %s", addr)
                close_connection = True
            else:
                response_writer = self._send_response(request, writer)
                if not response_writer or response_writer.wrote_connection_close:
                    close_connection = True

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

    def _send_response(self, request, writer):
        environ = self._get_environ(request)
        server_headers = self._get_server_headers(request)
        response_writer = WSGIResponseWriter(writer, server_headers)

        logger.debug("Calling into application")
        response_iter = self.application(environ, response_writer.start_response)
        logger.debug("Called into application")

        try:
            for response in response_iter:
                if response: # don't write empty strings
                    logger.debug("Write %s", response)
                    response_writer.write(response)

            if not response_writer.headers_sent or response_writer.wrote_transfer_encoding_chunked:
                # Force headers to be sent if nothing was written previously.
                # In the case of chunked encoding, write an empty (i.e. the last) chunk
                # to mark end of message
                response_writer.write(b"")

            return response_writer
        except Exception as e:
            logger.error("Application aborted: %r", e)
        finally:
            response_iter_close = getattr(response_iter, 'close', None)
            if callable(response_iter_close):
                response_iter.close()
            logger.debug("Called into application")

    def _send_error(self, status_line, writer):
        server_headers = [('Connection', 'close')]
        response_writer = WSGIResponseWriter(writer, server_headers)
        response_writer.start_response(status_line, [])
        response_writer.write(b'')
        return response_writer

    def _get_environ(self, request):
        environ = {
            'REQUEST_METHOD': request.method,
            'SCRIPT_NAME': '',
            'SERVER_NAME': self.hostname,
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

    def _get_server_headers(self, request):
        server_headers = []
        if request.headers.get('connection', '').lower() == 'close':
            server_headers.append(('Connection', 'close'))
        return server_headers

def start_new_worker(*args, **kwargs):
    worker = WSGIWorker(*args, **kwargs)
    worker.start()
    return worker
