import socket
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch

import pandas as pd
import pytest

from utils import config, network
from utils.playlist import CHANNEL_ID, ensure_columns, merge_visible_edits
from utils.proxy_server import LocalProxyServer
from utils.security import validate_target


def test_mixed_dns_answer_is_rejected():
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
    ]
    with patch("socket.getaddrinfo", return_value=answers):
        with pytest.raises(ValueError):
            validate_target("http://public.example/stream")


def test_redirect_to_private_target_is_blocked(http_source, monkeypatch):
    base, requests = http_source
    original = socket.getaddrinfo

    def dns(host, port, *args, **kwargs):
        if host == "public.example":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
        return original(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", dns)
    # Connect to a controlled server after validating the public initial URL.
    monkeypatch.setattr(
        network,
        "_connect",
        lambda *a, **k: socket.create_connection(
            ("127.0.0.1", int(urllib.parse.urlsplit(base).port)), timeout=2
        ),
    )
    with pytest.raises(ValueError):
        network.open_url("http://public.example/redirect", timeout=2)
    assert [request["path"] for request in requests] == ["/redirect"]


def test_manifest_routes_preserve_authority_and_authentication(http_source):
    base, _ = http_source
    proxy = LocalProxyServer(allow_private_networks=True)
    proxy.start()
    try:
        with urllib.request.urlopen(
            proxy.get_proxy_url(base + "/manifest.m3u8?provider=secret")
        ) as response:
            manifest = response.read().decode()
        routes = [line for line in manifest.splitlines() if line and not line.startswith("#")]
        assert len(routes) == 1
        assert routes[0].startswith("/proxy?token=" + proxy.token + "&url=")
        resolved = urllib.parse.parse_qs(urllib.parse.urlsplit(routes[0]).query)["url"][0]
        assert resolved == base + "/segment.ts?provider=secret"
        assert "key.bin%3Fprovider%3Dsecret" in manifest
        with urllib.request.urlopen(f"http://127.0.0.1:{proxy.port}" + routes[0]) as response:
            assert response.read() == b"LOCAL-STREAM"
    finally:
        proxy.stop()


def test_manifest_size_is_bounded(http_source, monkeypatch):
    monkeypatch.setattr(config, "MAX_MANIFEST_BYTES", 10)
    proxy = LocalProxyServer(allow_private_networks=True)
    proxy.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(proxy.get_proxy_url(http_source[0] + "/manifest.m3u8"))
        assert error.value.code == 400
        error.value.close()
    finally:
        proxy.stop()


def test_sessions_do_not_overwrite_each_others_lists():
    first, second = LocalProxyServer(), LocalProxyServer()
    first.start()
    second.start()
    try:
        first.set_m3u_content("#EXTM3U\nFIRST")
        second.set_m3u_content("#EXTM3U\nSECOND")
        for instance, expected in [(first, b"#EXTM3U\nFIRST"), (second, b"#EXTM3U\nSECOND")]:
            with urllib.request.urlopen(instance.endpoint_url("playlist.m3u")) as response:
                assert response.read() == expected
        first.stop()
        with urllib.request.urlopen(second.endpoint_url("playlist.m3u")) as response:
            assert response.read() == b"#EXTM3U\nSECOND"
    finally:
        first.stop()
        second.stop()


def test_head_and_range_use_provider_referer(http_source):
    base, requests = http_source
    proxy = LocalProxyServer(allow_private_networks=True)
    proxy.start()
    proxy.set_proxy_config(
        custom_referer="https://provider.example/", custom_user_agent="TestClient"
    )
    try:
        request = urllib.request.Request(proxy.get_proxy_url(base + "/stream.ts"), method="HEAD")
        with urllib.request.urlopen(request) as response:
            assert response.read() == b""
        request = urllib.request.Request(
            proxy.get_proxy_url(base + "/stream.ts"),
            headers={"Range": "bytes=0-11", "Referer": "http://localhost:8501/"},
        )
        with urllib.request.urlopen(request) as response:
            assert response.status == 206
            assert response.getheader("Content-Range") == "bytes 0-11/12"
        assert requests[0]["method"] == "HEAD"
        assert requests[1]["headers"]["Referer"] == "https://provider.example/"
        assert requests[1]["headers"]["User-Agent"] == "TestClient"
    finally:
        proxy.stop()


def test_visible_deletion_and_addition_preserve_hidden_metadata():
    original = ensure_columns(
        pd.DataFrame(
            [
                {
                    "Kanal Adı": "A",
                    "Grup": "A",
                    "URL": "https://example.com/a",
                    "LogoURL": "https://example.com/logo",
                },
                {
                    "Kanal Adı": "B",
                    "Grup": "B",
                    "URL": "https://example.com/b",
                    "_Attributes": {"tvg-id": "B"},
                },
            ]
        )
    )
    edited = pd.DataFrame(
        [{CHANNEL_ID: None, "Kanal Adı": "New", "Grup": "A", "URL": "https://example.com/new.mpd"}]
    )
    result = merge_visible_edits(original, [original.iloc[0][CHANNEL_ID]], edited)
    assert result["Kanal Adı"].tolist() == ["B", "New"]
    assert result.iloc[0]["_Attributes"] == {"tvg-id": "B"}
    assert result.iloc[1]["Tür"] == "DASH"
    assert result[CHANNEL_ID].is_unique


def test_invalid_edit_is_atomic():
    original = ensure_columns(pd.DataFrame([{"Kanal Adı": "A", "URL": "https://example.com/a"}]))
    edited = original.copy()
    edited.loc[0, "URL"] = "file:///private"
    with pytest.raises(ValueError):
        merge_visible_edits(original, original[CHANNEL_ID].tolist(), edited)
    assert original.iloc[0]["URL"] == "https://example.com/a"


def test_uploaded_bytes_respect_size_limit(monkeypatch):
    from utils.playlist import import_playlist

    monkeypatch.setattr(config, "MAX_FILE_SIZE_MB", 0)
    with pytest.raises(ValueError, match="MB"):
        import_playlist(b"#EXTM3U\n")


def test_rejected_published_pair_preserves_both_files(monkeypatch):
    proxy = LocalProxyServer()
    try:
        proxy.set_m3u_content("FIRST", "SECOND")
        monkeypatch.setattr(config, "MAX_FILE_SIZE_MB", 0.00001)
        with pytest.raises(ValueError):
            proxy.set_m3u_content("CHANGED", "x" * 100)
        from pathlib import Path

        assert Path(proxy.playlist_file).read_text(encoding="utf-8") == "FIRST"
        assert Path(proxy.proxied_playlist_file).read_text(encoding="utf-8") == "SECOND"
    finally:
        proxy.stop()
