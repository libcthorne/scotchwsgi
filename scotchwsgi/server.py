import asyncio
import functools
import logging
import socket
import ssl
import sys
from io import BytesIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WSGIAsyncReader(object):
    def __init__(self, reader, block_size=4096):
        self.reader = reader
        self.block_size = block_size
        self.bytes_buffer = b""

    async def fetch(self):
        data = await self.reader.read(self.block_size)
        self.bytes_buffer += data
        return len(data)

    async def read(self, size):
        while len(self.bytes_buffer) < size:
            fetched_len = await self.fetch()
            if fetched_len == 0:
                return b""

        blob = self.bytes_buffer[:size]
        self.bytes_buffer = self.bytes_buffer[size:]

        return blob

    async def readline(self):
        while b"\r\n" not in self.bytes_buffer:
            fetched_len = await self.fetch()
            if fetched_len == 0:
                return b""

        line, self.bytes_buffer = self.bytes_buffer.split(b"\r\n", 1)

        return line

class WSGIRequest(object):
    def __init__(self, method, path, query, http_version, headers, body):
        self.method = method
        self.path = path
        self.query = query
        self.http_version = http_version
        self.headers = headers
        self.body = body

    @staticmethod
    async def read_request_line(async_reader):
        request_line = (await async_reader.readline()).decode('ascii')
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
    async def read_headers(async_reader):
        headers = {}
        while True:
            header = (await async_reader.readline()).decode('ascii')
            if header == '':
                break

            header_name, header_value = header.split(':', 1)
            header_name = header_name.lower()
            header_value = header_value.lstrip()
            headers[header_name] = header_value

        logger.debug("Headers: %s", headers)

        return headers

    @staticmethod
    async def read_body(async_reader, content_length):
        if content_length > 0:
            logger.debug("Reading body")
            message_body = await async_reader.read(content_length)
            logger.debug("Body: %s", message_body)
        else:
            logger.debug("No body")
            message_body = b""

        return message_body

    @staticmethod
    async def from_async_reader(async_reader):
        method, path, query, http_version = await WSGIRequest.read_request_line(
            async_reader
        )

        headers = await WSGIRequest.read_headers(
            async_reader
        )

        body = await WSGIRequest.read_body(
            async_reader,
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

    async def _send_response(self, request, writer):
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
                writer.write(status.encode('ascii'))
                writer.write(b"\r\n")

                for header_name, header_value in response_headers:
                    writer.write(header_name.encode('ascii'))
                    writer.write(b": ")
                    writer.write(header_value.encode('ascii'))
                    writer.write(b"\r\n")

                writer.write(b"\r\n")

                headers_sent[:] = [status, response_headers]
                headers_to_send[:] = []

            writer.write(data)

        def start_response(status, response_headers, exc_info=None):
            logger.debug("start_response %s %s %s", status, response_headers, exc_info)

            if exc_info:
                try:
                    if headers_sent:
                        # reraise original exception if headers already sent
                        raise exc_info[1].with_traceback(exc_info[2])
                finally:
                    exc_info = None # avoid dangling circular ref
            elif headers_sent:
                raise AssertionError("Headers already set")

            headers_to_send[:] = [status, response_headers]

            return write

        logger.debug("Calling into application")
        loop = asyncio.get_event_loop()
        response_iter = await loop.run_in_executor(
            executor=None, # use default
            func=functools.partial(
                self.application,
                environ,
                start_response,
            ),
        )
        for response in response_iter:
            logger.debug("Write %s", response)
            write(response)

        response_iter_close = getattr(response_iter, 'close', None)
        if callable(response_iter_close):
            response_iter.close()
        logger.debug("Called into application")

        await writer.drain()

    async def handle_connection(self, reader, writer):
        logger.info("New connection: %s", writer.get_extra_info('peername'))

        request = await WSGIRequest.from_async_reader(WSGIAsyncReader(reader))
        await self._send_response(request, writer)

        logger.debug("Closing connection")
        writer.close()

    def start(self):
        loop = asyncio.get_event_loop()

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

        server_kwargs = {
            'loop': loop,
            'sock': sock,
        }
        if self.backlog:
            server_kwargs['backlog'] = self.backlog

        coro = asyncio.start_server(self.handle_connection, **server_kwargs)
        server = loop.run_until_complete(coro)

        logger.info("Listening on %s:%d", self.host, self.port)
        loop.run_forever()

def make_server(*args, **kwargs):
    return WSGIServer(*args, **kwargs)
