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
    def read_body(reader, content_length=None):
        if content_length is not None:
            logger.debug("Reading body (content-length: %d)", content_length)
            message_body = reader.read(content_length)
            logger.debug("Body: %s", message_body)

            if content_length != len(message_body):
                raise ValueError(
                    "content-length %d too large, only read %d bytes" % (
                        content_length, len(message_body)
                    )
                )
        else:
            logger.debug("Reading chunked body")
            message_body = b""

            while True:
                chunk_length_hex = reader.readline().rstrip()
                logger.debug("Chunk length hex: %s", chunk_length_hex)
                chunk_length = int(chunk_length_hex, 16)
                logger.debug("Reading chunk of length %d", chunk_length)
                if chunk_length == 0:
                    while reader.readline() not in (b"\r\n", b"\n"):
                        continue # Ignore trailer headers
                    break

                chunk_data = reader.read(chunk_length)
                logger.debug("Chunk: %r", chunk_data)
                chunk_newline = reader.readline()

                # Reconstruct message (though ideally the chunks should feed into the application as they arrive)
                message_body += chunk_data

        return message_body

    @staticmethod
    def from_reader(reader):
        method, path, query, http_version = WSGIRequest.read_request_line(
            reader
        )

        headers = WSGIRequest.read_headers(
            reader
        )

        transfer_encoding = headers.get('transfer-encoding')
        content_length = headers.get('content-length')

        if transfer_encoding:
            if transfer_encoding.lower() != 'chunked':
                raise NotImplementedError(
                    "Received unsupported transfer-encoding: %s" % transfer_encoding
                )

            body = WSGIRequest.read_body(reader)
        elif content_length:
            body = WSGIRequest.read_body(reader, int(content_length))
        else:
            body = b""

        return WSGIRequest(
            method=method,
            path=path,
            query=query,
            http_version=http_version,
            headers=headers,
            body=body,
        )
