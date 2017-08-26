import asyncio
import functools
import sys
from io import BytesIO

class AsyncReadBuffer(object):
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

class WSGIServer(object):
    def __init__(self, host, port, application):
        self.host = host
        self.port = port
        self.application = application

    async def handle_connection(self, reader, writer):
        print("New connection: {}".format(writer.get_extra_info('peername')))

        read_buffer = AsyncReadBuffer(reader)

        # Read request line
        request_line = (await read_buffer.readline()).decode('ascii')
        request_method, request_uri, http_version = request_line.split(' ', 3)
        request_uri_split = request_uri.split('?', 1)
        request_path = request_uri_split[0]
        if len(request_uri_split) > 1:
            request_query = request_uri_split[1]
        else:
            request_query = ''

        print("Read request line")
        print(request_method, request_uri, http_version)

        # Read request headers
        headers = {}
        reading_headers = True
        while reading_headers:
            header = (await read_buffer.readline()).decode('ascii')
            if header == '':
                reading_headers = False
                break

            header_name, header_value = header.split(':', 1)
            header_name = header_name.lower()
            header_value = header_value.lstrip()
            headers[header_name] = header_value

        print("Read headers")
        print(headers)

        if 'content-length' in headers:
            print("Reading body")
            # Read message body
            message_body = await read_buffer.read(int(headers['content-length']))
            print("Read body")
            print(message_body)
        else:
            print("No body")
            message_body = b""

        ################################################################

        # Send response

        environ = {
            'REQUEST_METHOD': request_method,
            'SCRIPT_NAME': '',
            'SERVER_NAME': self.host,
            'SERVER_PORT': str(self.port),
            'SERVER_PROTOCOL': http_version,
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'wsgi.input': BytesIO(message_body),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': True,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
        }

        headers_to_read = headers.copy()

        if request_path:
            environ['PATH_INFO'] = request_path
        if request_query:
            environ['QUERY_STRING'] = request_query
        if 'content-type' in headers:
            environ['CONTENT_TYPE'] = headers_to_read.pop('content-type')
        if 'content-length' in headers:
            environ['CONTENT_LENGTH'] = int(headers_to_read.pop('content-length'))

        for http_header_name, http_header_value in headers_to_read.items():
            http_header_name = 'HTTP_{}'.format(http_header_name.upper().replace('-', '_'))
            environ[http_header_name] = http_header_value

        headers_to_read.clear()

        headers_to_send = []
        headers_sent = []

        def write(data):
            if not headers_to_send and not headers_sent:
                raise AssertionError("write() before start_response()")

            elif not headers_sent:
                status, response_headers = headers_to_send[:]
                print("Send headers", status, response_headers)

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

        def start_response(status, response_headers):
            print("start_response", status, response_headers)

            headers_to_send[:] = [status, response_headers]

            return write

        print("Calling into application")
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
            print("Write", response)
            write(response)

        response_iter_close = getattr(response_iter, 'close', None)
        if callable(response_iter_close):
            response_iter.close()
        print("Called into application")

        await writer.drain()

        print("Closing connection")
        writer.close()

    def start(self):
        loop = asyncio.get_event_loop()
        coro = asyncio.start_server(
            self.handle_connection,
            self.host,
            self.port,
            loop=loop,
        )
        server = loop.run_until_complete(coro)

        print("Listening for connection...")
        loop.run_forever()
