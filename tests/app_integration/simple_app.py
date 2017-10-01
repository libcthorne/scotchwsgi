from wsgiref.validate import validator

# From PEP 3333
def app(environ, start_response):
    """Simplest possible application object"""
    status = '200 OK'

    if environ['QUERY_STRING'] == 'nobody':
        response = []
    else:
        response = [
            b"Hello world!\n",
            b"You sent a %s request" % (
                environ['REQUEST_METHOD'].encode('ascii')
            ),
        ]

    response_headers = [
        ('Content-type', 'text/plain'),
        ('Content-length', str(sum(len(line) for line in response))),
    ]
    start_response(status, response_headers)
    return response

app = validator(app)
