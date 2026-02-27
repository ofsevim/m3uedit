# M3U Editör Pro - Test Dosyası
# pytest ile çalıştırın: pytest tests/

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_parse_m3u_basic():
    """Temel M3U parse testi"""
    sample_m3u = [
        '#EXTM3U',
        '#EXTINF:-1 group-title="Test",Test Kanal',
        'http://example.com/stream.m3u8'
    ]
    
    # Parse fonksiyonunu test et
    # from app import parse_m3u_lines
    # channels = parse_m3u_lines(sample_m3u)
    # assert len(channels) == 1
    # assert channels[0]['Kanal Adı'] == 'Test Kanal'
    pass

def test_tr_filter():
    """TR filtresi testi"""
    # TR filtre fonksiyonunu test et
    pass

def test_convert_to_m3u():
    """M3U dönüştürme testi"""
    # DataFrame'den M3U'ya dönüştürme testi
    pass

# Daha fazla test eklenebilir
