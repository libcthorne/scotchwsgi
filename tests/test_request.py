import unittest
from io import BytesIO

from scotchwsgi.request import WSGIRequest

class TestRequestLine(unittest.TestCase):
    def test_request_line_empty(self):
        reader = BytesIO(b'')
        self.assertRaises(
            ValueError,
            WSGIRequest.read_request_line,
            reader
        )

    def test_request_line_missing_path(self):
        reader = BytesIO(b'GET ')
        self.assertRaises(
            ValueError,
            WSGIRequest.read_request_line,
            reader
        )

    def test_request_line_missing_http_version(self):
        reader = BytesIO(b'GET /')
        self.assertRaises(
            ValueError,
            WSGIRequest.read_request_line,
            reader
        )

    def test_request_line_full(self):
        reader = BytesIO(b'GET / HTTP/1.1')
        self.assertEqual(
            WSGIRequest.read_request_line(reader),
            ('GET', '/', '', 'HTTP/1.1')
        )

    def test_request_line_full_with_query(self):
        reader = BytesIO(b'GET /?a=1&b=2 HTTP/1.1')
        self.assertEqual(
            WSGIRequest.read_request_line(reader),
            ('GET', '/', 'a=1&b=2', 'HTTP/1.1')
        )

class TestRequestHeaders(unittest.TestCase):
    def test_no_headers(self):
        reader = BytesIO(b'')
        self.assertDictEqual(
            WSGIRequest.read_headers(reader),
            {}
        )

    def test_missing_header_value(self):
        reader = BytesIO(b'Header-Name-Only')
        self.assertRaises(
            ValueError,
            WSGIRequest.read_headers,
            reader
        )

    def test_valid_header_value(self):
        reader = BytesIO(b'Header: value')
        self.assertDictEqual(
            WSGIRequest.read_headers(reader),
            {'header': 'value'}
        )

    def test_valid_header_value_with_whitespace(self):
        reader = BytesIO(b'Header:     value')
        self.assertDictEqual(
            WSGIRequest.read_headers(reader),
            {'header': 'value'}
        )

    def test_valid_header_values_crlf_delimiter(self):
        reader = BytesIO(b'Header-One: value one\r\nHeader-Two: value two')
        self.assertDictEqual(
            WSGIRequest.read_headers(reader),
            {
                'header-one': 'value one',
                'header-two': 'value two',
            }
        )

    def test_valid_header_values_newline_delimiter(self):
        reader = BytesIO(b'Header-One: value one\nHeader-Two: value two')
        self.assertDictEqual(
            WSGIRequest.read_headers(reader),
            {
                'header-one': 'value one',
                'header-two': 'value two',
            }
        )

class TestRequestBody(unittest.TestCase):
    def test_no_body(self):
        reader = BytesIO(b'')
        self.assertEqual(
            WSGIRequest.read_body(reader, 0),
            b''
        )

    def test_content_length_too_large(self):
        reader = BytesIO(b'123456789')
        self.assertRaises(
            ValueError,
            WSGIRequest.read_body,
            reader,
            100
        )

    def test_valid_body(self):
        reader = BytesIO(b'123456789')
        self.assertEqual(
            WSGIRequest.read_body(reader, 9),
            b'123456789'
        )

    def test_chunked_body(self):
        reader = BytesIO(b'5\r\nhello\r\n5\r\nworld\r\n0\r\n\r\n')
        self.assertEqual(
            WSGIRequest.read_body(reader),
            b'helloworld'
        )

class TestRequestReader(unittest.TestCase):
    def test_request_line_only(self):
        reader = BytesIO(b'GET /?a=1 HTTP/1.1\r\n')
        request = WSGIRequest.from_reader(reader)

        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.path, '/')
        self.assertEqual(request.query, 'a=1')
        self.assertEqual(request.http_version, 'HTTP/1.1')

        self.assertDictEqual(request.headers, {})

        self.assertEqual(request.body, b'')

    def test_request_line_and_headers(self):
        reader = BytesIO(b'GET /?a=1 HTTP/1.1\r\nheader-one: value-one\r\nheader-two: value-two\r\n\r\n')
        request = WSGIRequest.from_reader(reader)

        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.path, '/')
        self.assertEqual(request.query, 'a=1')
        self.assertEqual(request.http_version, 'HTTP/1.1')

        self.assertDictEqual(
            request.headers,
            {
                'header-one': 'value-one',
                'header-two': 'value-two',
            }
        )

        self.assertEqual(request.body, b'')

    def test_request_line_and_headers_and_body(self):
        reader = BytesIO(b'GET /?a=1 HTTP/1.1\r\nheader-one: value-one\r\ncontent-length: 5\r\n\r\nHello')
        request = WSGIRequest.from_reader(reader)

        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.path, '/')
        self.assertEqual(request.query, 'a=1')
        self.assertEqual(request.http_version, 'HTTP/1.1')

        self.assertDictEqual(
            request.headers,
            {
                'header-one': 'value-one',
                'content-length': '5',
            }
        )

        self.assertEqual(
            request.body,
            b'Hello'
        )

    def test_request_line_and_headers_and_body_chunked(self):
        reader = BytesIO(b'GET /?a=1 HTTP/1.1\r\nheader-one: value-one\r\ntransfer-encoding: chunked\r\n\r\n5\r\nHello\r\n0\r\n\r\n')
        request = WSGIRequest.from_reader(reader)

        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.path, '/')
        self.assertEqual(request.query, 'a=1')
        self.assertEqual(request.http_version, 'HTTP/1.1')

        self.assertDictEqual(
            request.headers,
            {
                'header-one': 'value-one',
                'transfer-encoding': 'chunked',
            }
        )

        self.assertEqual(
            request.body,
            b'Hello'
        )
