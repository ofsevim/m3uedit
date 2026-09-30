import ipaddress
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture(autouse=True)
def offline_network(monkeypatch):
    """Tests may use local fixtures, never IPTV providers or publishing services."""
    original = socket.socket.connect
    from utils import config

    monkeypatch.setattr(config, "PROXY_PORT", 0)
    monkeypatch.setattr(config, "PROXY_BIND_HOST", "127.0.0.1")
    monkeypatch.setattr(config, "PROXY_PUBLIC_BASE_URL", "")
    monkeypatch.setattr(config, "ALLOW_PRIVATE_NETWORKS", False)

    def connect(sock, address):
        if isinstance(address, tuple):
            try:
                local = ipaddress.ip_address(address[0]).is_loopback
            except ValueError:
                local = address[0] == "localhost"
            if not local:
                raise OSError("External network disabled in tests")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)


@pytest.fixture
def http_source():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            requests.append(
                {"path": self.path, "headers": dict(self.headers), "method": self.command}
            )
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1/private")
                self.end_headers()
                return
            payload = b"LOCAL-STREAM"
            mime = "video/mp2t"
            if self.path.startswith("/manifest.m3u8"):
                payload = b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin"\nsegment.ts\n'
                mime = "application/vnd.apple.mpegurl"
            self.send_response(206 if self.headers.get("Range") else 200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            if self.headers.get("Range"):
                self.send_header("Content-Range", "bytes 0-11/12")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
