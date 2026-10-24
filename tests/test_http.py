import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import load_config
from core.http import (
    _SafeRedirectHandler,
    _release_response_bytes,
    _reserve_response_bytes,
    _take_request_slot,
    _validate_public_url,
    fetch,
    request_budget,
)


class URLValidation(unittest.TestCase):
    def setUp(self):
        load_config()

    def test_rejects_non_http_schemes(self):
        self.assertIsNotNone(_validate_public_url("file:///etc/passwd"))

    def test_rejects_credentials(self):
        self.assertIsNotNone(_validate_public_url("https://user:pass@example.com/"))

    def test_rejects_non_public_ip_literals(self):
        for address in ("127.0.0.1", "10.0.0.1", "169.254.1.1", "::1", "fc00::1", "::ffff:127.0.0.1"):
            with self.subTest(address=address):
                self.assertIsNotNone(_validate_public_url(f"http://{address}/"))

    @mock.patch("core.http.socket.getaddrinfo")
    def test_rejects_hostname_with_non_public_resolution(self, resolve):
        resolve.return_value = [
            (2, 1, 6, "", ("93.184.216.34", 80)),
            (2, 1, 6, "", ("192.168.1.2", 80)),
        ]
        self.assertIsNotNone(_validate_public_url("http://example.com/"))

    @mock.patch("core.http.socket.getaddrinfo")
    def test_accepts_public_hostname_resolution(self, resolve):
        resolve.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        self.assertIsNone(_validate_public_url("http://example.com/"))

    def test_redirect_handler_rejects_private_destination(self):
        handler = _SafeRedirectHandler()
        with self.assertRaises(URLError):
            handler.redirect_request(None, None, 302, "Found", {}, "http://127.0.0.1/")

    def test_fetch_rejects_private_destination_before_network_access(self):
        with mock.patch("core.http.build_opener") as build_opener, \
             mock.patch("core.http.cache.load", return_value=None):
            result = fetch("http://127.0.0.1/")
        self.assertFalse(result["ok"])
        self.assertIn("non-public", result["error"])
        build_opener.assert_not_called()

    def test_request_budget_limits_requests_and_response_bytes(self):
        load_config(overrides={"http": {
            "max_requests_per_run": 1,
            "max_total_response_bytes": 8,
        }})

        @request_budget
        def check_budget():
            self.assertIsNone(_take_request_slot())
            self.assertEqual(_take_request_slot(), "Maximum HTTP requests per scan reached")
            reserved = _reserve_response_bytes(6)
            self.assertEqual(reserved, 6)
            _release_response_bytes(reserved, 4)
            self.assertEqual(_reserve_response_bytes(6), 4)
            self.assertEqual(_reserve_response_bytes(6), 0)

        check_budget()

    def test_request_budget_stops_after_deadline(self):
        load_config(overrides={"http": {"max_run_seconds": 1}})

        @request_budget
        def check_deadline():
            self.assertEqual(_take_request_slot(), "Maximum scan time reached")

        with mock.patch("core.http.time.monotonic", side_effect=[100.0, 102.0]):
            check_deadline()


class FetchBody(unittest.TestCase):
    def setUp(self):
        load_config(overrides={"cache": {"enabled": False}})

    def response(self, payload):
        reply = mock.MagicMock()
        reply.__enter__.return_value = reply
        reply.status = 200
        reply.geturl.return_value = "https://example.com/"
        reply.headers = {}
        reply.read.side_effect = lambda n: payload[:n]
        opener = mock.MagicMock()
        opener.open.return_value = reply
        return opener

    @mock.patch("core.http._validate_public_url", return_value=None)
    def test_reads_body_and_flags_truncation(self, _):
        load_config(overrides={"cache": {"enabled": False}, "http": {"max_response_bytes": 10}})
        with mock.patch("core.http.build_opener", return_value=self.response(b"x" * 10)):
            result = fetch("https://example.com/")
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], b"x" * 10)
        self.assertFalse(result["truncated"])
        with mock.patch("core.http.build_opener", return_value=self.response(b"x" * 25)):
            result = fetch("https://example.com/")
        self.assertEqual(result["data"], b"x" * 10)
        self.assertTrue(result["truncated"])

    @mock.patch("core.http._validate_public_url", return_value=None)
    def test_budget_counts_fetches(self, _):
        load_config(overrides={"cache": {"enabled": False}, "http": {"max_requests_per_run": 2}})

        @request_budget
        def run():
            with mock.patch("core.http.build_opener", return_value=self.response(b"ok")):
                return [fetch("https://example.com/")["ok"] for _ in range(3)], \
                       fetch("https://example.com/")["error"]

        results, error = run()
        self.assertEqual(results, [True, True, False])
        self.assertEqual(error, "Maximum HTTP requests per scan reached")


if __name__ == "__main__":
    unittest.main()
