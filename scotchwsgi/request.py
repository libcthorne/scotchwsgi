import logging

from scotchwsgi import const

logger = logging.getLogger(__name__)

class WSGIRequest(object):
    def __init__(self, method, path, query, http_version, headers, body):
        self.method = method
        self.path = path
        self.query = query
        self.http_version = http_version
        self.headers = headers
        self.body = body

    @staticmethod
    def read_request_line(reader):
        request_line = reader.readline().decode(const.STR_ENCODING)
        logger.info("Received request %s", request_line)

        try:
            request_method, request_uri, http_version = request_line.split(' ', 3)
        except ValueError:
            raise ValueError("Invalid request line: %s" % request_line)

        http_version = http_version.rstrip()
        request_uri_split = request_uri.split('?', 1)
        request_path = request_uri_split[0]
        if len(request_uri_split) > 1:
            request_query = request_uri_split[1]
        else:
            request_query = ''

        return request_method, request_path, request_query, http_version

    @staticmethod
    def read_headers(reader):
        headers = {}
        while True:
            header = reader.readline().decode(const.STR_ENCODING).replace('\r\n', '\n').rstrip('\n')
            if header == '':
                break

            try:
                header_name, header_value = header.split(':', 1)
            except ValueError:
                raise ValueError("Invalid header: %s" % header)

            header_name = header_name.lower()
            header_value = header_value.lstrip()
            headers[header_name] = header_value

        logger.debug("Headers: %s", headers)

        return headers

    @staticmethod
    def read_body(reader, content_length):
        if content_length > 0:
            logger.debug("Reading body")
            message_body = reader.read(content_length)
            logger.debug("Body: %s", message_body)
        else:
            logger.debug("No body")
            message_body = b""

        if content_length != len(message_body):
            raise ValueError(
                "content-length %d too large, only read %d bytes" % (
                    content_length, len(message_body)
                )
            )

        return message_body

    @staticmethod
    def from_reader(reader):
        method, path, query, http_version = WSGIRequest.read_request_line(
            reader
        )

        headers = WSGIRequest.read_headers(
            reader
        )

        body = WSGIRequest.read_body(
            reader,
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
