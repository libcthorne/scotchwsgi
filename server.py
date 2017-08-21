import socket
import sys
from io import BytesIO

class ReadBuffer(object):
    def __init__(self, conn, block_size=4096):
        self.conn = conn
        self.block_size = block_size
        self.bytes_buffer = b""

    def fetch(self):
        data = self.conn.recv(self.block_size)
        self.bytes_buffer += data
        return len(data)

    def read(self, size):
        while len(self.bytes_buffer) < size:
            fetched_len = self.fetch()
            if fetched_len == 0:
                return b""

        blob = self.bytes_buffer[:size]
        self.bytes_buffer = self.bytes_buffer[size:]

        return blob

    def readline(self):
        while b"\r\n" not in self.bytes_buffer:
            fetched_len = self.fetch()
            if fetched_len == 0:
                return b""

        line, self.bytes_buffer = self.bytes_buffer.split(b"\r\n", 1)

        return line

class WSGIServer(object):
    def __init__(self, host, port, application):
        self.host = host
        self.port = port
        self.application = application
        self.socket = socket.socket()
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def handle_connection(self, conn):
        read_buffer = ReadBuffer(conn)

        # Read request line
        request_line = read_buffer.readline()
        request_method, request_uri, http_version = request_line.split(b' ', 3)
        request_uri_split = request_uri.split(b'?', 1)
        request_path = request_uri_split[0]
        if len(request_uri_split) > 1:
            request_query = request_uri_split[1]
        else:
            request_query = b""

        print("Read request line")
        print(request_method, request_uri, http_version)

        # Read request headers
        headers = {}
        reading_headers = True
        while reading_headers:
            header = read_buffer.readline()
            if header == b"":
                reading_headers = False
                break

            header_name, header_value = header.split(b':', 1)
            header_name = header_name.lower()
            header_value = header_value.lstrip()
            headers[header_name] = header_value

        print("Read headers")
        print(headers)

        if b'content-length' in headers:
            print("Reading body")
            # Read message body
            message_body = read_buffer.read(int(headers[b'content-length']))
            print("Read body")
            print(message_body)
        else:
            print("No body")
            message_body = b""

        ################################################################

        # Send response

        # WIP
        environ = {
            'REQUEST_METHOD': request_method,
            'SERVER_NAME': self.host,
            'SERVER_PORT': str(self.port),
            'SERVER_PROTOCOL': http_version.decode('ascii'),
            'wsgi.input': BytesIO(message_body),
            'wsgi.errors': sys.stdout,
            'wsgi.url_scheme': 'http',
        }

        if request_path:
            environ['PATH_INFO'] = request_path.decode('ascii')
        if request_query:
            environ['QUERY_STRING'] = request_query.decode('ascii')
        if b'content-type' in headers:
            environ['CONTENT_TYPE'] = headers[b'content-type'].decode('ascii')
        if b'content-length' in headers:
            environ['CONTENT_LENGTH'] = int(headers[b'content-length'])
        if b'host' in headers:
            environ['HTTP_HOST'] = headers[b'host'].decode('ascii')

        def start_response(status, response_headers):
            print("start_response", status, response_headers)

            conn.send(b"HTTP/1.0 ")
            conn.send(status.encode('ascii'))
            conn.send(b"\r\n")

            for header_name, header_value in response_headers:
                conn.send(header_name.encode('ascii'))
                conn.send(b": ")
                conn.send(header_value.encode('ascii'))
                conn.send(b"\r\n")

            conn.send(b"\r\n")

        for response in self.application(environ, start_response):
            print("Write", response)
            conn.send(response)

        print("Closing connection")
        conn.close()

    def start(self):
        self.socket.bind((self.host, self.port))
        self.socket.listen()
        self.accepting_connections = True

        while self.accepting_connections:
            print("Listening for connection...")
            conn, addr = self.socket.accept()
            print("New connection: {}".format(addr))
            self.handle_connection(conn)
