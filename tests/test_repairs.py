import threading
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from utils import network, parser
from utils.proxy_server import LocalProxyServer


def test_m3u_roundtrip_preserves_comma_names_epg_and_directives():
    source = [
        '#EXTM3U x-tvg-url="https://example.com/epg.xml"',
        '#EXTINF:-1 tvg-id="news" group-title="News, World",News, East',
        "#EXTVLCOPT:http-referrer=https://example.com",
        "https://example.com/live.m3u8",
    ]
    channels = parser.parse_m3u_lines(source)
    assert channels[0]["Kanal Adı"] == "News, East"
    result = parser.convert_df_to_m3u(pd.DataFrame(channels))
    assert 'x-tvg-url="https://example.com/epg.xml"' in result
    assert 'tvg-id="news"' in result
    assert "#EXTVLCOPT:http-referrer=https://example.com" in result


def test_progress_callbacks_run_in_calling_thread():
    caller = threading.get_ident()
    calls = []
    with patch.object(parser, "_check_single_url", return_value="active"):
        result = parser.batch_check_health(
            ["https://example.com/1", "https://example.com/2"],
            progress_callback=lambda count, total: calls.append((threading.get_ident(), count)),
        )
    assert result == ["active", "active"]
    assert calls == [(caller, 1), (caller, 2)]


@pytest.mark.parametrize(
    "url",
    [
        "file:///review.m3u",
        "ftp://example.com/a",
        "http://127.0.0.1/a",
        "http://169.254.169.254/a",
        "http://[::1]/a",
    ],
)
def test_import_rejects_non_public_targets(url):
    with pytest.raises(ValueError):
        network.fetch_m3u_source(url, user_agent="Test", timeout=1, disable_ssl_verify=False)


def test_proxy_instances_have_separate_files_and_default_local_binding():
    first, second = LocalProxyServer(), LocalProxyServer()
    try:
        assert first.playlist_file != second.playlist_file
        first.start()
        assert first.server.server_address[0] == "127.0.0.1"
    finally:
        first.stop()
        second.stop()


def test_proxy_rejects_unauthenticated_playlist_reads():
    server = LocalProxyServer()
    server.start()
    try:
        server.set_m3u_content("#EXTM3U\nPRIVATE\n")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(f"http://127.0.0.1:{server.port}/playlist.m3u", timeout=2)
        assert error.value.code == 403
        error.value.close()
    finally:
        server.stop()


def test_player_url_cannot_close_script_element():
    from utils.player import render_live_player

    malicious = "https://example.com/</script><script>window.REVIEW=1</script>"
    try:
        result = render_live_player(malicious, proxy_base_url="/relay?token=test")
    except ValueError:
        return
    assert "</script><script>window.REVIEW=1</script>" not in result


@pytest.fixture
def app(tmp_path, monkeypatch):
    from utils.visitor_counter import VisitorCounter

    monkeypatch.setattr(
        VisitorCounter, "_resolve_path", staticmethod(lambda name: str(tmp_path / name))
    )
    import streamlit as st

    st.cache_resource.clear()
    servers = []
    original_start = LocalProxyServer.start

    def start(server):
        servers.append(server)
        return original_start(server)

    monkeypatch.setattr(LocalProxyServer, "start", start)
    instance = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    instance.session_state.data = pd.DataFrame(
        [
            {
                "Grup": "A",
                "Kanal Adı": "First",
                "URL": "https://example.com/1",
                "LogoURL": "https://example.com/logo1",
                "Tür": "HLS",
                "Durum": "Pending",
            },
            {
                "Grup": "B",
                "Kanal Adı": "Second",
                "URL": "https://example.com/2",
                "LogoURL": "https://example.com/logo2",
                "Tür": "HLS",
                "Durum": "Pending",
            },
        ]
    )
    instance.run()
    assert not instance.exception
    yield instance
    for server in servers:
        server.stop()
    st.cache_resource.clear()


def test_filtered_save_preserves_unseen_rows_and_logos(app):
    app.multiselect(key="group_filter").set_value(["A"]).run()
    next(
        b for b in app.button if b.label == "💾 Tablodaki Düzenlemeleri Listeye Kaydet"
    ).click().run()
    assert not app.exception
    assert len(app.session_state.data) == 2
    assert app.session_state.data["LogoURL"].tolist() == [
        "https://example.com/logo1",
        "https://example.com/logo2",
    ]


def test_empty_import_does_not_clear_current_playlist(app):
    next(b for b in app.button if b.label == "🚀 Listeyi Çek ve Tara").click().run()
    assert not app.exception
    assert len(app.session_state.data) == 2


def test_failed_import_does_not_clear_current_playlist(app):
    next(w for w in app.text_input if w.label == "🌐 M3U Linki Yapıştır:").set_value(
        "https://example.com/broken"
    )
    with patch.object(network, "fetch_m3u_source", side_effect=ValueError("Invalid playlist")):
        next(b for b in app.button if b.label == "🚀 Listeyi Çek ve Tara").click().run()
    assert not app.exception
    assert len(app.session_state.data) == 2


def test_local_logo_path_is_not_rendered(app, tmp_path):
    private = tmp_path / "private.svg"
    private.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>PRIVATE-LOCAL</text></svg>', encoding="utf-8"
    )
    app.session_state.data.loc[0, "LogoURL"] = str(private)
    app.run()
    selector = app.selectbox(key="player_tab_select_box")
    selector.set_value(selector.options[1]).run()
    assert not app.exception
    assert app.session_state.play_channel is not None
    assert len(app.get("image")) == 0


def test_new_channel_without_logo_can_be_selected(app):
    app.session_state.data = pd.concat(
        [
            app.session_state.data,
            pd.DataFrame([{"Kanal Adı": "New", "URL": "https://example.com/new"}]),
        ],
        ignore_index=True,
    )
    app.run()
    selector = app.selectbox(key="player_tab_select_box")
    selector.set_value(selector.options[-1]).run()
    assert not app.exception
    assert app.session_state.play_channel["name"] == "New"


def test_cloud_ui_routes_http_channel_through_adentv_with_selected_device_profile(app):
    from urllib.parse import parse_qs, urlsplit

    from tests.test_player import execute_player

    url = "http://provider.example/play?extension=ts&play_token=test"
    app.session_state.data.loc[0, "URL"] = url
    app.selectbox(key="tab_vpn_profile_select").set_value("VLC Media Player").run()
    app.text_input(key="tab_vpn_ref_input").set_value("https://provider.example/").run()
    selector = app.selectbox(key="player_tab_select_box")
    selector.set_value(selector.options[1]).run()
    assert not app.exception
    result = execute_player(app.get("iframe")[0].proto.srcdoc)
    assert result["sources"][0]["engine"] == "MPEGTS"
    target = urlsplit(result["sources"][0]["url"])
    assert target.netloc == "adentv-canli.netlify.app"
    assert parse_qs(target.query) == {
        "url": [url],
        "format": ["ts"],
        "ua": ["VLC/3.0.18 LibVLC/3.0.18"],
        "referer": ["https://provider.example/"],
    }


def test_changing_headers_during_playback_updates_the_cloud_stream_immediately(app):
    from urllib.parse import parse_qs, urlsplit

    from tests.test_player import execute_player

    app.session_state.data.loc[0, "URL"] = "http://provider.example/live.ts"
    app.run()
    selector = app.selectbox(key="player_tab_select_box")
    selector.set_value(selector.options[1]).run()
    app.selectbox(key="tab_vpn_profile_select").set_value("VLC Media Player").run()
    result = execute_player(app.get("iframe")[0].proto.srcdoc)
    params = parse_qs(urlsplit(result["sources"][0]["url"]).query)
    assert params["ua"] == ["VLC/3.0.18 LibVLC/3.0.18"]
    app.text_input(key="tab_vpn_ref_input").set_value("https://provider.example/").run()
    result = execute_player(app.get("iframe")[0].proto.srcdoc)
    params = parse_qs(urlsplit(result["sources"][0]["url"]).query)
    assert params["referer"] == ["https://provider.example/"]


def test_stop_player_clears_selection(app):
    selector = app.selectbox(key="player_tab_select_box")
    selector.set_value(selector.options[1]).run()
    next(button for button in app.button if button.label == "⏹ Durdur").click().run()
    assert not app.exception
    assert app.session_state.play_channel is None
    assert app.selectbox(key="player_tab_select_box").value == "Seçiniz..."


def test_interchannel_directives_survive_roundtrip():
    channels = parser.parse_m3u_lines(
        [
            "#EXTM3U",
            "#EXTINF:-1,A",
            "https://example.com/a",
            "#EXTVLCOPT:http-referrer=https://example.com/",
            "#EXTINF:-1,B",
            "https://example.com/b",
            "#END-OF-PLAYLIST",
        ]
    )
    result = parser.convert_df_to_m3u(pd.DataFrame(channels))
    assert "https://example.com/a\n#EXTVLCOPT:http-referrer=https://example.com/" in result
    assert result.endswith("https://example.com/b\n#END-OF-PLAYLIST\n")
