from unittest.mock import patch

from utils import network


class MockResponse:
    def __init__(self, payload: bytes, lines: list[bytes] | None = None):
        self.payload = payload
        self._lines = lines or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.payload

    def readlines(self) -> list[bytes]:
        return list(self._lines)


def test_create_ssl_context_disables_verification():
    context = network.create_ssl_context(True)
    assert context.check_hostname is False


def test_fetch_m3u_source_returns_lines():
    response = MockResponse(b"", [b"#EXTM3U\n", b"http://example.com/live.m3u8\n"])

    with patch("urllib.request.urlopen", return_value=response):
        lines = network.fetch_m3u_source(
            "http://example.com/list.m3u",
            user_agent="TestAgent",
            timeout=5,
            disable_ssl_verify=True,
        )

    assert lines == [b"#EXTM3U\n", b"http://example.com/live.m3u8\n"]


def test_create_m3u_link_falls_back_to_dpaste():
    fallback_response = MockResponse(b"https://dpaste.com/abcd")

    with patch("urllib.request.urlopen", side_effect=[RuntimeError("paste.rs down"), fallback_response]):
        link = network.create_m3u_link(
            "#EXTM3U\n",
            user_agent="TestAgent",
            disable_ssl_verify=True,
            timeout=5,
        )

    assert link == "https://dpaste.com/abcd.txt"
