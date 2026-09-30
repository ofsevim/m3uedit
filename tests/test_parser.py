# M3U Editor Pro parser tests

from unittest.mock import patch

import pandas as pd

from utils import parser as parser_utils
from utils.parser import convert_df_to_m3u, filter_channels, parse_m3u_lines


def test_parse_m3u_basic():
    sample = [
        "#EXTM3U",
        '#EXTINF:-1 group-title="Test",Test Kanal',
        "http://example.com/stream.m3u8",
    ]
    channels = parse_m3u_lines(sample)
    assert len(channels) == 1
    assert channels[0]["Kanal Adı"] == "Test Kanal"
    assert channels[0]["Grup"] == "Test"
    assert channels[0]["URL"] == "http://example.com/stream.m3u8"


def test_parse_m3u_multiple_channels():
    sample = [
        "#EXTM3U",
        '#EXTINF:-1 group-title="Spor",Spor Kanalı',
        "http://example.com/spor.m3u8",
        '#EXTINF:-1 group-title="Haber",Haber Kanalı',
        "http://example.com/haber.m3u8",
    ]
    channels = parse_m3u_lines(sample)
    assert len(channels) == 2


def test_parse_m3u_with_logo():
    sample = [
        "#EXTM3U",
        '#EXTINF:-1 tvg-logo="http://logo.com/img.png" group-title="Film",Film Kanalı',
        "http://example.com/film.m3u8",
    ]
    channels = parse_m3u_lines(sample)
    assert channels[0]["LogoURL"] == "http://logo.com/img.png"


def test_parse_m3u_no_group():
    sample = [
        "#EXTM3U",
        "#EXTINF:-1,Adsız Kanal",
        "http://example.com/stream.m3u8",
    ]
    channels = parse_m3u_lines(sample)
    assert channels[0]["Grup"] == "Genel"


def test_parse_m3u_bytes():
    sample = [
        b"#EXTM3U",
        b'#EXTINF:-1 group-title="Test",Byte Kanal',
        b"http://example.com/stream.m3u8",
    ]
    channels = parse_m3u_lines(sample)
    assert channels[0]["Kanal Adı"] == "Byte Kanal"


def test_parse_m3u_empty():
    assert len(parse_m3u_lines([])) == 0


def test_parse_url_type_detection():
    sample = [
        "#EXTM3U",
        '#EXTINF:-1 group-title="A",HLS Kanal',
        "http://example.com/live/stream.m3u8",
        '#EXTINF:-1 group-title="B",DASH Kanal',
        "http://example.com/stream.mpd",
    ]
    channels = parse_m3u_lines(sample)
    assert channels[0]["Tür"] == "HLS"
    assert channels[1]["Tür"] == "DASH"


def test_explicit_stream_format_takes_priority_over_live_path():
    assert parser_utils.detect_type("https://example.com/live/account/channel.ts") == "MPEG-TS"
    assert parser_utils.detect_type("https://example.com/live/account/channel.mpd") == "DASH"
    assert parser_utils.detect_type("https://example.com/live/account/channel.mp4") == "Diğer"


def test_filter_channels_tr():
    channels = [
        {"Grup": "TR | Spor", "Kanal Adı": "Spor", "URL": "http://a.com"},
        {"Grup": "UK | News", "Kanal Adı": "News", "URL": "http://b.com"},
        {"Grup": "TURKIYE Haber", "Kanal Adı": "Haber", "URL": "http://c.com"},
    ]
    filtered = filter_channels(channels, only_tr=True)
    assert len(filtered) == 2


def test_filter_channels_no_filter():
    channels = [{"Grup": "UK | News", "Kanal Adı": "News", "URL": "http://b.com"}]
    assert len(filter_channels(channels, only_tr=False)) == 1


def test_filter_channels_keyword():
    channels = [
        {"Grup": "Spor", "Kanal Adı": "beIN Sports", "URL": "http://a.com"},
        {"Grup": "Haber", "Kanal Adı": "CNN Türk", "URL": "http://b.com"},
    ]
    filtered = filter_channels(channels, keyword="bein")
    assert len(filtered) == 1


def test_filter_channels_group():
    channels = [
        {"Grup": "Spor", "Kanal Adı": "A", "URL": "http://a.com"},
        {"Grup": "Haber", "Kanal Adı": "B", "URL": "http://b.com"},
    ]
    assert len(filter_channels(channels, group_filter="Spor")) == 1


def test_convert_df_to_m3u():
    df = pd.DataFrame(
        [
            {"Grup": "Test", "Kanal Adı": "Kanal 1", "URL": "http://a.com", "LogoURL": ""},
            {
                "Grup": "Test",
                "Kanal Adı": "Kanal 2",
                "URL": "http://b.com",
                "LogoURL": "http://logo.com/img.png",
            },
        ]
    )
    m3u = convert_df_to_m3u(df)
    assert m3u.startswith("#EXTM3U")
    assert "Kanal 1" in m3u
    assert 'tvg-logo="http://logo.com/img.png"' in m3u


def test_batch_check_health_progress_is_consistent():
    urls = ["http://a.com", "http://b.com", "http://c.com"]
    progress_calls = []
    mock_status = "ACTIVE"

    with patch.object(parser_utils, "_check_single_url", return_value=mock_status):
        results = parser_utils.batch_check_health(
            urls,
            max_workers=3,
            timeout=0.1,
            progress_callback=lambda completed, total: progress_calls.append((completed, total)),
        )

    assert results == [mock_status, mock_status, mock_status]
    assert sorted(call[0] for call in progress_calls) == [1, 2, 3]
    assert all(call[1] == 3 for call in progress_calls)


def test_convert_df_to_proxied_m3u():
    df = pd.DataFrame(
        [
            {
                "Grup": "Spor",
                "Kanal Adı": "Canlı Maç",
                "URL": "http://stream.com/live.m3u8",
                "LogoURL": "",
            },
        ]
    )
    proxied_m3u = parser_utils.convert_df_to_proxied_m3u(df, "http://192.168.1.50:8888/proxy")
    assert proxied_m3u.startswith("#EXTM3U")
    assert "http://192.168.1.50:8888/proxy?url=http%3A%2F%2Fstream.com%2Flive.m3u8" in proxied_m3u


def test_convert_df_to_csv_json_txt():
    df = pd.DataFrame(
        [
            {
                "Grup": "Haber",
                "Kanal Adı": "Haber TV",
                "URL": "http://haber.com/stream.m3u8",
                "Tür": "HLS",
                "Durum": "✅ Aktif",
                "LogoURL": "",
            },
        ]
    )
    csv_out = parser_utils.convert_df_to_csv(df)
    assert "Haber TV" in csv_out
    assert "http://haber.com/stream.m3u8" in csv_out

    json_out = parser_utils.convert_df_to_json(df)
    import json

    data = json.loads(json_out)
    assert len(data) == 1
    assert data[0]["Kanal Adı"] == "Haber TV"
    assert data[0]["URL"] == "http://haber.com/stream.m3u8"

    txt_out = parser_utils.convert_df_to_txt(df)
    assert txt_out.strip() == "http://haber.com/stream.m3u8"


def test_check_single_url_geo_blocked_vpn_detection():
    import urllib.error

    err_403 = urllib.error.HTTPError("http://geoblocked.com", 403, "Forbidden", {}, None)
    with patch("utils.network.open_url", side_effect=err_403):
        res = parser_utils._check_single_url("http://geoblocked.com")
        assert res == "🌍 VPN Gerekebilir"
