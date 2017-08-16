#! /usr/bin/env python
# -*- coding: utf-8 -*-

import socketserver

HOST = "localhost"
PORT = 8080

class RequestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        print("Received request")

        while True:
            data = self.rfile.readline()
            print(data)
            if data == b'\r\n': break

        html = "<p>Hello</p>"
        self.request.sendall("HTTP/1.0 200 OK\nContent-Type: text/html; charset=utf-8\nContent-Length: {}\n\n{}\n".format(
            len(html),
            html,
        ).encode('ascii'))

if __name__ == "__main__":
    with socketserver.TCPServer((HOST, PORT), RequestHandler) as server:
        server.serve_forever()
