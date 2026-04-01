# M3U Editör Pro - Test Dosyası
# pytest ile çalıştırın: pytest tests/

import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app import parse_m3u_lines, filter_channels, convert_df_to_m3u
import pandas as pd
from utils import parser as parser_utils


# =====================================================================
# PARSE TESTLERİ
# =====================================================================

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


# =====================================================================
# FİLTRE TESTLERİ
# =====================================================================

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


# =====================================================================
# DÖNÜŞÜM TESTLERİ
# =====================================================================

def test_convert_df_to_m3u():
    df = pd.DataFrame([
        {"Grup": "Test", "Kanal Adı": "Kanal 1", "URL": "http://a.com", "LogoURL": ""},
        {"Grup": "Test", "Kanal Adı": "Kanal 2", "URL": "http://b.com", "LogoURL": "http://logo.com/img.png"},
    ])
    m3u = convert_df_to_m3u(df)
    assert m3u.startswith("#EXTM3U")
    assert "Kanal 1" in m3u
    assert 'tvg-logo="http://logo.com/img.png"' in m3u


def test_batch_check_health_progress_is_consistent():
    urls = ["http://a.com", "http://b.com", "http://c.com"]
    progress_calls = []

    with patch.object(parser_utils, "_check_single_url", return_value="âœ… Aktif"):
        results = parser_utils.batch_check_health(
            urls,
            max_workers=3,
            timeout=0.1,
            progress_callback=lambda completed, total: progress_calls.append((completed, total)),
        )

    assert results == ["âœ… Aktif", "âœ… Aktif", "âœ… Aktif"]
    assert sorted(call[0] for call in progress_calls) == [1, 2, 3]
    assert all(call[1] == 3 for call in progress_calls)
