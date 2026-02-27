# M3U Editör Pro - Test Dosyası
# pytest ile çalıştırın: pytest tests/

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app import parse_m3u_lines, filter_channels, convert_df_to_m3u
import pandas as pd


def test_parse_m3u_basic():
    """Temel M3U parse testi."""
    sample_m3u = [
        "#EXTM3U",
        '#EXTINF:-1 group-title="Test",Test Kanal',
        "http://example.com/stream.m3u8",
    ]
    channels = parse_m3u_lines(sample_m3u)
    assert len(channels) == 1
    assert channels[0]["Kanal Adı"] == "Test Kanal"
    assert channels[0]["Grup"] == "Test"
    assert channels[0]["URL"] == "http://example.com/stream.m3u8"


def test_parse_m3u_multiple_channels():
    """Birden fazla kanal parse testi."""
    sample_m3u = [
        "#EXTM3U",
        '#EXTINF:-1 group-title="Spor",Spor Kanalı',
        "http://example.com/spor.m3u8",
        '#EXTINF:-1 group-title="Haber",Haber Kanalı',
        "http://example.com/haber.m3u8",
    ]
    channels = parse_m3u_lines(sample_m3u)
    assert len(channels) == 2
    assert channels[0]["Kanal Adı"] == "Spor Kanalı"
    assert channels[1]["Kanal Adı"] == "Haber Kanalı"


def test_parse_m3u_with_logo():
    """Logo URL parse testi."""
    sample_m3u = [
        "#EXTM3U",
        '#EXTINF:-1 tvg-logo="http://logo.com/img.png" group-title="Film",Film Kanalı',
        "http://example.com/film.m3u8",
    ]
    channels = parse_m3u_lines(sample_m3u)
    assert len(channels) == 1
    assert channels[0]["LogoURL"] == "http://logo.com/img.png"


def test_parse_m3u_no_group():
    """Grup bilgisi olmayan kanal parse testi."""
    sample_m3u = [
        "#EXTM3U",
        "#EXTINF:-1,Adsız Kanal",
        "http://example.com/stream.m3u8",
    ]
    channels = parse_m3u_lines(sample_m3u)
    assert len(channels) == 1
    assert channels[0]["Grup"] == "Genel"


def test_parse_m3u_bytes():
    """Byte satırları parse testi."""
    sample_m3u = [
        b"#EXTM3U",
        b'#EXTINF:-1 group-title="Test",Byte Kanal',
        b"http://example.com/stream.m3u8",
    ]
    channels = parse_m3u_lines(sample_m3u)
    assert len(channels) == 1
    assert channels[0]["Kanal Adı"] == "Byte Kanal"


def test_parse_m3u_empty():
    """Boş M3U parse testi."""
    channels = parse_m3u_lines([])
    assert len(channels) == 0


def test_filter_channels_tr():
    """TR filtresi testi."""
    channels = [
        {"Grup": "TR | Spor", "Kanal Adı": "Spor", "URL": "http://a.com"},
        {"Grup": "UK | News", "Kanal Adı": "News", "URL": "http://b.com"},
        {"Grup": "TURKIYE Haber", "Kanal Adı": "Haber", "URL": "http://c.com"},
    ]
    filtered = filter_channels(channels, only_tr=True)
    assert len(filtered) == 2
    assert all("TR" in ch["Grup"] or "TURKIYE" in ch["Grup"] for ch in filtered)


def test_filter_channels_no_filter():
    """Filtre kapalıyken tüm kanallar dönmeli."""
    channels = [
        {"Grup": "UK | News", "Kanal Adı": "News", "URL": "http://b.com"},
    ]
    filtered = filter_channels(channels, only_tr=False)
    assert len(filtered) == 1


def test_convert_df_to_m3u():
    """DataFrame'den M3U dönüştürme testi."""
    df = pd.DataFrame(
        [
            {"Grup": "Test", "Kanal Adı": "Kanal 1", "URL": "http://a.com", "LogoURL": ""},
            {"Grup": "Test", "Kanal Adı": "Kanal 2", "URL": "http://b.com", "LogoURL": "http://logo.com/img.png"},
        ]
    )
    m3u = convert_df_to_m3u(df)
    assert m3u.startswith("#EXTM3U")
    assert "Kanal 1" in m3u
    assert "Kanal 2" in m3u
    assert "http://a.com" in m3u
    assert "http://b.com" in m3u
