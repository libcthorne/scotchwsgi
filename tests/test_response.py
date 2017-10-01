import sys
import unittest
from io import BytesIO

from scotchwsgi.response import WSGIResponseWriter

class TestResponseWriter(unittest.TestCase):
    def setUp(self):
        self.out = b''
        self.writer = BytesIO(self.out)
        self.response_writer = WSGIResponseWriter(self.writer)

    def test_start_response_once_without_exc_info(self):
        """PEP 3333: the ``start_response`` callable **must not**
        actually transmit the response headers.  Instead, it must
        store them for the server or gateway to transmit **only**
        after the first iteration of the application return value that
        yields a non-empty bytestring, or upon the application's first
        invocation of the ``write()`` callable.
        """
        self.response_writer.start_response(
            '200',
            [('Header', 'Value')]
        )

        self.assertEqual(self.response_writer.headers_to_send[0], '200')
        self.assertIn(('Header', 'Value'), self.response_writer.headers_to_send[1])
        self.assertEqual(self.response_writer.headers_sent, [])

    def test_start_response_multiple_without_exc_info(self):
        """PEP 3333: it is a fatal error to call ``start_response``
        without the ``exc_info`` argument if ``start_response`` has
        already been called within the current invocation of the
        application.  This includes the case where the first call to
        ``start_response`` raised an error.
        """
        self.response_writer.start_response(
            '200',
            [('Header', 'Value')]
        )

        self.assertRaises(
            AssertionError,
            self.response_writer.start_response,
            '200',
            [('New-Header', 'New-Value')]
        )

        self.assertEqual(self.response_writer.headers_to_send[0], '200')
        self.assertIn(('Header', 'Value'), self.response_writer.headers_to_send[1])
        self.assertEqual(self.response_writer.headers_sent, [])

    def test_start_response_once_with_exc_info(self):
        """PEP 3333: the ``start_response`` callable **must not**
        actually transmit the response headers.  Instead, it must
        store them for the server or gateway to transmit **only**
        after the first iteration of the application return value that
        yields a non-empty bytestring, or upon the application's first
        invocation of the ``write()`` callable.

        The ``exc_info`` argument, if supplied, must be a Python
        ``sys.exc_info()`` tuple.  This argument should be supplied by
        the application only if ``start_response`` is being called by
        an error handler.  If ``exc_info`` is supplied, and no HTTP
        headers have been output yet, ``start_response`` should
        replace the currently-stored HTTP response headers with the
        newly-supplied ones, thus allowing the application to "change
        its mind" about the output when an error has occurred.
        """
        try:
            raise Exception('Test')
        except:
            self.response_writer.start_response(
                '500',
                [('Header', 'Value')],
                exc_info=sys.exc_info(),
            )

        self.assertEqual(self.response_writer.headers_to_send[0], '500')
        self.assertIn(('Header', 'Value'), self.response_writer.headers_to_send[1])
        self.assertEqual(self.response_writer.headers_sent, [])

    def test_start_response_multiple_with_exc_info(self):
        """PEP 3333: The application **may** call ``start_response``
        more than once, if and only if the ``exc_info`` argument is
        provided.

        If ``exc_info`` is supplied, and no HTTP headers have been
        output yet, ``start_response`` should replace the
        currently-stored HTTP response headers with the newly-supplied
        ones, thus allowing the application to "change its mind" about
        the output when an error has occurred.
        """
        try:
            raise Exception('Test')
        except:
            self.response_writer.start_response(
                '500',
                [('Header', 'Value')],
                exc_info=sys.exc_info(),
            )

        try:
            raise Exception('Test two')
        except:
            self.response_writer.start_response(
                '501',
                [('New-Header', 'New-Value')],
                exc_info=sys.exc_info(),
            )

        self.assertEqual(self.response_writer.headers_to_send[0], '501')
        self.assertIn(('New-Header', 'New-Value'), self.response_writer.headers_to_send[1])
        self.assertEqual(self.response_writer.headers_sent, [])

    def test_start_response_without_exc_info_after_exc_info(self):
        """PEP 3333: It is a fatal error to call ``start_response``
        without the ``exc_info`` argument if ``start_response`` has
        already been called within the current invocation of the
        application.  This includes the case where the first call to
        ``start_response`` raised an error.
        """
        try:
            raise Exception('Test')
        except:
            self.response_writer.start_response(
                '500',
                [('Header', 'Value')],
                exc_info=sys.exc_info(),
            )

        self.assertRaises(
            AssertionError,
            self.response_writer.start_response,
            '200',
            [('New-Header', 'New-Value')]
        )

        self.assertEqual(self.response_writer.headers_to_send[0], '500')
        self.assertIn(('Header', 'Value'), self.response_writer.headers_to_send[1])
        self.assertEqual(self.response_writer.headers_sent, [])

    def test_write_before_start_response(self):
        """
        PEP 3333: the application **must** invoke the
        ``start_response()`` callable before the iterable yields its
        first body bytestring, so that the server can send the headers
        before any body content.
        """
        self.assertRaises(
            AssertionError,
            self.response_writer.write,
            b'',
        )

    def test_write_after_start_response(self):
        """
        PEP 3333: the application **must** invoke the
        ``start_response()`` callable before the iterable yields its
        first body bytestring, so that the server can send the headers
        before any body content.
        """
        self.response_writer.start_response(
            '200',
            [('Header', 'Value')]
        )
        self.response_writer.write(b'Test')

    def test_start_response_after_write(self):
        """
        PEP 3333: If no output has been written when an exception
        occurs, the call to ``start_response`` will return normally,
        and the application will return an error body to be sent to
        the browser.  However, if any output has already been sent to
        the browser, ``start_response`` will reraise the provided
        exception.
        """
        self.response_writer.start_response(
            '200',
            [('Header', 'Value')]
        )
        self.response_writer.write(b'Test')

        try:
            raise Exception('Test')
        except:
            self.assertRaises(
                Exception,
                self.response_writer.start_response,
                '500',
                [('Header', 'Value')],
                exc_info=sys.exc_info(),
            )
