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
    def __init__(self, application, sock, hostname, parent_pid):
        self.application = application
        self.sock = sock
        self.hostname = hostname
        _, self.port = sock.getsockname()
        self.parent_pid = parent_pid

    def start(self):
        logger.info("Worker starting (PID: %d)", os.getpid())

        # Ignore interrupts to disable KeyboardInterrupt being logged
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        gevent.monkey.patch_all()
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

        try:
            request = WSGIRequest.from_reader(reader)
        except ValueError:
            # TODO: Send invalid request response
            pass
        else:
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

    def _send_response(self, request, writer):
        environ = self._get_environ(request)
        response_writer = WSGIResponseWriter(writer)

        logger.debug("Calling into application")
        response_iter = self.application(environ, response_writer.start_response)

        try:
            for response in response_iter:
                logger.debug("Write %s", response)
                response_writer.write(response)
        except Exception as e:
            logger.error("Application aborted: %r", e)
        finally:
            response_iter_close = getattr(response_iter, 'close', None)
            if callable(response_iter_close):
                response_iter.close()
            logger.debug("Called into application")

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
