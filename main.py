#! /usr/bin/env python
# -*- coding: utf-8 -*-

import socketserver

HOST = "localhost"
PORT = 8080

# From PEP 3333
def simple_app(environ, start_response):
    """Simplest possible application object"""
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)
    return [b"Hello world!\n", b"testing!"]

class RequestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        print("Received request")

        # Read request line
        request_line = self.rfile.readline().decode('ascii')
        method, uri, http_version = request_line[:-2].split(' ')

        # Read request headers
        request_headers = {}
        while True:
            header_line = self.rfile.readline().decode('ascii')
            if header_line == '\r\n': break
            header_name, header_value = header_line[:-2].split(':', 1)
            header_name = header_name.lower()
            header_value = header_value.lstrip()
            request_headers[header_name] = header_value

        # Read body
        if 'content-length' in request_headers:
            content_length = int(request_headers['content-length'])
            body = self.rfile.read(content_length).decode('ascii')
        else:
            body = ""

        ################################################################

        # Send response

        environ = {} # TODO

        def start_response(status, response_headers):
            self.wfile.write(b"HTTP/1.0 ")
            self.wfile.write(status.encode('ascii'))
            self.wfile.write(b"\r\n")

            for header_name, header_value in response_headers:
                self.wfile.write(header_name.encode('ascii'))
                self.wfile.write(b": ")
                self.wfile.write(header_value.encode('ascii'))
                self.wfile.write(b"\r\n")

            self.wfile.write(b"\r\n")

        for response in simple_app(environ, start_response):
            self.wfile.write(response)

        self.wfile.close()

if __name__ == "__main__":
    with socketserver.TCPServer((HOST, PORT), RequestHandler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

        server.server_close()
