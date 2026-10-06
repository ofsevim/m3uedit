"""Playback routing regressions, executed without contacting any IPTV provider."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from utils.player import render_live_player


def run_player(
    url, *, page="https://m3uedit.streamlit.app/", proxy="", use_proxy=True, referrer=None
):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required to execute the embedded player regression tests")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("player_runtime.cjs"))],
        input=json.dumps(
            {
                "html": render_live_player(url, proxy_base_url=proxy, use_proxy=use_proxy),
                "page": page,
                "referrer": referrer,
            }
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=10,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "url,engine",
    [
        ("https://provider.example/play/live.php?id=454&extension=ts&play_token=test", "MPEGTS"),
        ("https://provider.example/live.ts?play_token=m3u8", "MPEGTS"),
        ("https://provider.example/play?extension=TS", "MPEGTS"),
        ("https://provider.example/play?extension=m3u8&play_token=ts", "HLS"),
        ("https://provider.example/live.m3u8?play_token=ts", "HLS"),
        ("https://provider.example/movie.mp4?play_token=ts", "native"),
    ],
)
def test_stream_format_selects_engine_and_preserves_provider_parameters(url, engine):
    assert run_player(url)["sources"] == [{"engine": engine, "url": url}]


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def test_cloud_player_does_not_send_stream_to_viewers_loopback(host):
    url = "https://provider.example/live.ts?play_token=test"
    result = run_player(url, proxy=f"http://{host}:8502/proxy?token=session")
    assert result["sources"] == [{"engine": "MPEGTS", "url": url}]


def test_local_player_keeps_its_session_proxy():
    result = run_player(
        "https://provider.example/live.ts?play_token=test",
        page="http://localhost:8501/",
        proxy="http://127.0.0.1:8502/proxy?token=session",
    )
    assert result["sources"] == [
        {
            "engine": "MPEGTS",
            "url": "http://127.0.0.1:8502/proxy?token=session&url="
            "https%3A%2F%2Fprovider.example%2Flive.ts%3Fplay_token%3Dtest",
        }
    ]


def test_cloud_player_keeps_configured_https_gateway():
    result = run_player(
        "https://provider.example/live.ts",
        proxy="https://gateway.example/relay/proxy?token=session",
    )
    assert result["sources"] == [
        {
            "engine": "MPEGTS",
            "url": "https://gateway.example/relay/proxy?token=session&url="
            "https%3A%2F%2Fprovider.example%2Flive.ts",
        }
    ]


def test_disabling_proxy_uses_original_stream():
    url = "https://provider.example/live.m3u8"
    result = run_player(url, proxy="https://gateway.example/proxy?token=test", use_proxy=False)
    assert result["sources"] == [{"engine": "HLS", "url": url}]


def test_http_stream_on_cloud_explains_https_gateway_requirement():
    result = run_player(
        "http://provider.example/live.ts",
        proxy="http://127.0.0.1:8502/proxy?token=session",
    )
    assert result["sources"] == []
    assert "HTTPS" in result["message"]
    assert "proxy" in result["message"]


def test_srcdoc_without_referrer_preserves_local_proxy():
    result = run_player(
        "https://provider.example/live.ts",
        page="http://localhost:8501/",
        referrer="",
        proxy="http://127.0.0.1:8502/proxy?token=session",
    )
    assert result["sources"] == [
        {
            "engine": "MPEGTS",
            "url": "http://127.0.0.1:8502/proxy?token=session&url="
            "https%3A%2F%2Fprovider.example%2Flive.ts",
        }
    ]


def test_srcdoc_without_referrer_still_explains_mixed_content():
    result = run_player("http://provider.example/live.ts", referrer="")
    assert result["sources"] == []
    assert "HTTPS" in result["message"]
