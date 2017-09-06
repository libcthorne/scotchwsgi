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
    def read_headers(reader):
        headers = {}
        while True:
            header = reader.readline().decode(const.STR_ENCODING).replace('\r\n', '\n').rstrip('\n')
            if header == '':
                break

            header_name, header_value = header.split(':', 1)
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
