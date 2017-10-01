import sys
from wsgiref.validate import validator

def error_before_write(start_response):
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)

    # simulate an exception here, before headers are written
    status = '500 ERROR'
    response_headers = [
        ('Content-type', 'text/plain'),
        ('Content-length', str(len(b"Something went wrong"))),
    ]
    start_response(status, response_headers, sys.exc_info())

    return [
        b"Something went wrong",
    ]

def error_after_write(start_response):
    status = '200 OK'
    response_headers = [
        ('Content-type', 'text/plain'),
        ('Content-length', str(len(b"So far so good")+len(b"Don't send me"))),
    ]
    start_response(status, response_headers)

    def error():
        # simulate an exception here, after headers are written
        raise Exception("something bad happened")

    try:
        yield b"So far so good"
        error()
    except:
        status = '500 ERROR'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers, sys.exc_info())
        yield b"Don't send me"

def app(environ, start_response):
    route = environ['PATH_INFO']
    if route == '/error_before_write':
        return error_before_write(start_response)
    elif route == '/error_after_write':
        return error_after_write(start_response)
    else:
        raise AssertionError("Unknown route %s" % route)

app = validator(app)
