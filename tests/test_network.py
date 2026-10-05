import io
import ssl
import time
from unittest.mock import patch

import pytest

from utils import network


class MockResponse(io.BytesIO):
    headers = {}


def test_create_ssl_context_disables_verification():
    assert network.create_ssl_context(True).check_hostname is False


def test_default_tls_verifies_certificates():
    context = network.create_ssl_context()
    assert context.check_hostname
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_fetch_m3u_source_returns_lines():
    with patch.object(
        network, "open_url", return_value=MockResponse(b"#EXTM3U\nhttp://example.com/live.m3u8\n")
    ):
        lines = network.fetch_m3u_source(
            "http://example.com/list.m3u", user_agent="Test", timeout=5
        )
    assert lines == [b"#EXTM3U\n", b"http://example.com/live.m3u8\n"]


def test_create_m3u_link_requires_consent():
    with pytest.raises(ValueError, match="onay"):
        network.create_m3u_link("#EXTM3U\n", user_agent="Test")


def test_selected_service_returns_verified_share_link():
    requests = []

    def respond(request, **options):
        requests.append((request.full_url, options["disable_ssl_verify"]))
        return MockResponse(b"https://dpaste.com/abcd")

    with patch.object(network, "open_url", side_effect=respond):
        link = network.create_m3u_link(
            "#EXTM3U\n",
            user_agent="Test",
            service="dpaste.com",
            consent=True,
            disable_ssl_verify=True,
        )
    assert link == "https://dpaste.com/abcd.txt"
    assert requests == [("https://dpaste.com/api/v2/", False)]


def test_sharing_does_not_fall_back_to_other_service():
    with patch.object(network, "open_url", side_effect=OSError("offline")):
        with pytest.raises(OSError):
            network.create_m3u_link("#EXTM3U", user_agent="Test", consent=True)


def test_share_service_cannot_return_another_host():
    with patch.object(
        network, "open_url", return_value=MockResponse(b"https://attacker.example/link")
    ):
        with pytest.raises(ValueError):
            network.create_m3u_link("#EXTM3U", user_agent="Test", consent=True)


def test_paste_rs_rejects_oversized_and_partial_uploads():
    oversized = "#EXTM3U\n" + ("#EXTINF:-1,Ch\nhttps://example.com/1.m3u8\n" * 2000)
    with pytest.raises(ValueError, match="64 KB"):
        network.create_m3u_link(
            oversized, user_agent="Test", service="paste.rs", consent=True
        )

    partial = MockResponse(b"https://paste.rs/abc")
    partial.status = 206
    with patch.object(network, "open_url", return_value=partial):
        with pytest.raises(ValueError, match="eksik"):
            network.create_m3u_link(
                "#EXTM3U\n", user_agent="Test", service="paste.rs", consent=True
            )


def test_catbox_service_returns_verified_files_link():
    with patch.object(
        network, "open_url", return_value=MockResponse(b"https://files.catbox.moe/abc123.m3u")
    ):
        link = network.create_m3u_link(
            "#EXTM3U\n#EXTINF:-1,Test\nhttps://example.com/1.m3u8\n",
            user_agent="Test",
            service="catbox.moe",
            consent=True,
        )
    assert link == "https://files.catbox.moe/abc123.m3u"



def test_fetch_m3u_source_with_headers_and_proxy():
    received = []

    def respond(request, **options):
        received.append(
            (request.get_header("Referer"), request.get_header("User-agent"), options["proxy_url"])
        )
        return MockResponse(b"#EXTM3U\nhttp://example.com/vpn.m3u8\n")

    with patch.object(network, "open_url", side_effect=respond):
        lines = network.fetch_m3u_source(
            "http://example.com/list.m3u",
            user_agent="TiviMate/4.7.0",
            timeout=5,
            proxy_url="http://127.0.0.1:10808",
            headers={"Referer": "https://iptv.com"},
        )
    assert lines[1] == b"http://example.com/vpn.m3u8\n"
    assert received == [("https://iptv.com", "TiviMate/4.7.0", "http://127.0.0.1:10808")]


def test_size_limit_without_content_length_or_newlines():
    with pytest.raises(ValueError, match="boyutu"):
        network.read_bounded(MockResponse(b"x" * 100), 10)


def test_size_limit_at_exact_boundary():
    assert network.read_bounded(MockResponse(b"1234567890"), 10) == b"1234567890"


def test_redirect_bodies_are_not_drained():
    from urllib.request import Request

    response = MockResponse(b"x" * 200000)
    handler = network._RedirectHandler(False)

    class Parent:
        def open(self, request, timeout):
            return "redirected"

    handler.parent = Parent()
    request = Request("http://example.com/start")
    request.timeout = 1
    consumed = []
    original_read = response.read

    def read(*args):
        result = original_read(*args)
        consumed.append(len(result))
        return result

    response.read = read
    with patch.object(network, "validate_target"):
        result = handler.http_error_302(
            request, response, 302, "redirect", {"location": "http://example.com/final"}
        )
    assert result == "redirected"
    assert consumed == []


def test_download_deadline_interrupts_dripping_body():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "40")
            self.end_headers()
            try:
                for _ in range(40):
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(0.03)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with network.open_url(
            f"http://127.0.0.1:{server.server_port}/", allow_private=True, timeout=0.2
        ) as response:
            start = time.monotonic()
            with pytest.raises(TimeoutError):
                network.read_bounded(response, 100, deadline_seconds=0.12)
            assert time.monotonic() - start < 0.6
    finally:
        server.shutdown()
        server.server_close()


def test_download_deadline_interrupts_dripping_chunk_header():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                for byte in b"000000000000000000001\r\nx\r\n0\r\n\r\n":
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    time.sleep(0.03)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with network.open_url(
            f"http://127.0.0.1:{server.server_port}/", allow_private=True, timeout=0.2
        ) as response:
            start = time.monotonic()
            with pytest.raises(TimeoutError):
                network.read_bounded(response, 100, deadline_seconds=0.1)
            assert time.monotonic() - start < 0.5
    finally:
        server.shutdown()
        server.server_close()
