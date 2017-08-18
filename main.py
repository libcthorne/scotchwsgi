#! /usr/bin/env python
# -*- coding: utf-8 -*-

import socket

HOST = "localhost"
PORT = 8080

# From PEP 3333
def simple_app(environ, start_response):
    """Simplest possible application object"""
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)
    return [b"Hello world!\n", b"testing!"]

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
            # Read message body
            message_body = read_buffer.read(int(headers[b'content-length']))
            print("Read body")
            print(message_body)
        else:
            message_body = b""

        ################################################################

        # Send response

        environ = {} # TODO

        def start_response(status, response_headers):
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

if __name__ == '__main__':
    server = WSGIServer(HOST, PORT, simple_app)
    server.start()
