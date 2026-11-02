"""Exercise the actual HTTP response reader with in-memory sockets, never TLS bypass."""
import http.client
import io
import ssl
import unittest
from unittest.mock import Mock, patch

from backend.app.payments.errors import MalformedResponse, ProviderTimeout, ProviderUnavailable
from backend.app.payments.paypal_client import MAX_RESPONSE_BYTES, SandboxTransport
from backend.tests.payments.fakes import INVOICE_ID


class MemorySocket:
    def __init__(self, wire):
        self.file = io.BytesIO(wire)
        self.timeouts = []

    def makefile(self, mode):
        return self.file

    def settimeout(self, timeout):
        self.timeouts.append(timeout)


class TransportTests(unittest.TestCase):
    def request(self):
        return SandboxTransport().request("GET", "/v2/invoicing/invoices/" + INVOICE_ID, {}, None, 10)

    def wire_response(self, wire):
        sock = MemorySocket(wire)
        connection = Mock()
        connection.sock = sock

        def getresponse():
            response = http.client.HTTPResponse(sock, method="GET")
            response.begin()
            # Simulate http.client transferring the socket to a closing response.
            connection.sock = None
            return response

        connection.getresponse.side_effect = getresponse
        self.addCleanup(lambda: self.assertTrue(sock.file.closed))
        self.addCleanup(connection.close.assert_called_once)
        replacement = patch("backend.app.payments.paypal_client.http.client.HTTPSConnection", return_value=connection)
        replacement.start()
        self.addCleanup(replacement.stop)
        return connection, sock

    def test_complete_response_with_detached_socket(self):
        _, sock = self.wire_response(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}')
        self.assertEqual(self.request().body, b"{}")
        self.assertTrue(all(0 < value <= 10 for value in sock.timeouts))

    def test_truncated_content_length_is_transport_failure_even_if_json_is_valid(self):
        self.wire_response(b'HTTP/1.1 200 OK\r\nContent-Length: 200\r\n\r\n{}')
        with self.assertRaises(ProviderUnavailable):
            self.request()

    def test_chunked_response_and_truncated_chunks(self):
        self.wire_response(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n')
        self.assertEqual(self.request().body, b"{}")

    def test_truncated_chunk_is_transport_failure(self):
        self.wire_response(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n20\r\n{}')
        with self.assertRaises(ProviderUnavailable):
            self.request()

    def test_oversize_stream_is_rejected_and_closed(self):
        self.wire_response(b'HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n' + b"x" * (MAX_RESPONSE_BYTES + 1))
        with self.assertRaises(MalformedResponse):
            self.request()

    def test_deadline_checked_between_reads(self):
        self.wire_response(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}')
        with patch("backend.app.payments.paypal_client.time.monotonic", side_effect=[0, 1, 2, 11]):
            with self.assertRaises(ProviderTimeout):
                self.request()

    def test_tls_and_connection_errors_are_sanitized_and_closed(self):
        for error, expected in ((ssl.SSLCertVerificationError("private diagnostic"), ProviderUnavailable),
                                (TimeoutError("private diagnostic"), ProviderTimeout),
                                (OSError("private diagnostic"), ProviderUnavailable)):
            with self.subTest(error=type(error)), patch("backend.app.payments.paypal_client.http.client.HTTPSConnection") as factory:
                connection = factory.return_value
                connection.connect.side_effect = error
                with self.assertRaises(expected) as caught:
                    self.request()
                self.assertNotIn("private diagnostic", str(caught.exception))
                self.assertEqual(factory.call_args.kwargs["context"].verify_mode, ssl.CERT_REQUIRED)
                connection.request.assert_not_called()
                connection.close.assert_called_once()

    def test_redirect_body_is_not_read_or_followed(self):
        connection, sock = self.wire_response(b'HTTP/1.1 302 Found\r\nLocation: https://example.test/\r\nContent-Length: 100\r\n\r\n')
        self.assertEqual(self.request().status, 302)
        connection.request.assert_called_once()
