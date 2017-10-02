import logging

from scotchwsgi import const

logger = logging.getLogger(__name__)

class WSGIResponseHeaders(object):
    def __init__(self, server_headers, app_headers):
        self.response_headers = []
        self.has_connection_close = False
        self.has_content_length = False
        self.has_transfer_encoding_chunked = False

        for header_name, header_value in server_headers:
            self.response_headers.append((header_name, header_value))

            if header_name.lower() == 'connection':
                if header_value.lower() == 'close':
                    self.has_connection_close = True

        for header_name, header_value in app_headers:
            self.response_headers.append((header_name, header_value))

            if header_name.lower() == 'content-length':
                self.has_content_length = True

        if not self.has_content_length and not self.has_connection_close:
            self.response_headers.append(('Transfer-Encoding', 'chunked'))
            self.has_transfer_encoding_chunked = True

    def __iter__(self):
        return iter(self.response_headers)

class WSGIResponseWriter(object):
    def __init__(self, writer, server_headers=None):
        self.writer = writer
        self.headers_to_send = []
        self.headers_sent = []
        self.server_headers = server_headers or []
        self.wrote_last_chunk = False

    def start_response(self, status, app_headers, exc_info=None):
        logger.debug("start_response %s %s %s", status, app_headers, exc_info)

        if exc_info:
            try:
                if self.headers_sent:
                    logger.debug("Reraising application exception")
                    # reraise original exception if headers already sent
                    raise exc_info[1].with_traceback(exc_info[2])
            finally:
                exc_info = None # avoid dangling circular ref
        elif self.headers_to_send:
            raise AssertionError("Headers already set")

        response_headers = WSGIResponseHeaders(
            self.server_headers,
            app_headers,
        )

        self.headers_to_send[:] = [status, response_headers]

        return self.write

    def write(self, data):
        if not self.headers_to_send:
            raise AssertionError("write() before start_response()")

        if self.wrote_last_chunk:
            raise AssertionError("write() after last chunk written")

        elif not self.headers_sent:
            status, response_headers = self.headers_to_send[:]
            logger.debug("Send headers %s %s", status, response_headers)

            self.writer.write(b"HTTP/1.1 ")
            self.writer.write(status.encode(const.STR_ENCODING))
            self.writer.write(b"\r\n")

            for header_name, header_value in response_headers:
                self.writer.write(header_name.encode(const.STR_ENCODING))
                self.writer.write(b": ")
                self.writer.write(header_value.encode(const.STR_ENCODING))
                self.writer.write(b"\r\n")

            self.writer.write(b"\r\n")

            self.headers_sent[:] = [status, response_headers]

        if self.wrote_transfer_encoding_chunked:
            chunk_size = len(data)
            chunk_size_hex = b"%0.2X" % len(data)

            self.writer.write(chunk_size_hex)
            self.writer.write(b"\r\n")

            if chunk_size > 0:
                self.writer.write(data)
                self.writer.write(b"\r\n")
            else:
                self.wrote_last_chunk = True
                self.writer.write(b"\r\n") # marks end of chunked encoding
        else:
            self.writer.write(data)

        self.writer.flush()

    @property
    def wrote_connection_close(self):
        status_, response_headers = self.headers_sent
        return response_headers.has_connection_close

    @property
    def wrote_transfer_encoding_chunked(self):
        status_, response_headers = self.headers_sent
        return response_headers.has_transfer_encoding_chunked
