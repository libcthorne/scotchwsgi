import logging

from scotchwsgi import const

logger = logging.getLogger(__name__)

class WSGIResponseWriter(object):
    def __init__(self, writer, server_headers=None):
        self.writer = writer
        self.headers_to_send = []
        self.headers_sent = []
        self.server_headers = server_headers
        self.wrote_content_length = False

    def start_response(self, status, app_headers, exc_info=None):
        response_headers = self._get_response_headers(app_headers)

        logger.debug("start_response %s %s %s", status, response_headers, exc_info)

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

        self.headers_to_send[:] = [status, response_headers]

        return self.write

    def write(self, data):
        if not self.headers_to_send:
            raise AssertionError("write() before start_response()")

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

                if header_name.lower() == 'content-length':
                    self.wrote_content_length = True

            self.writer.write(b"\r\n")

            self.headers_sent[:] = [status, response_headers]

        self.writer.write(data)
        self.writer.flush()

    def _get_response_headers(self, app_headers):
        if self.server_headers:
            return self.server_headers + app_headers
        else:
            return app_headers
