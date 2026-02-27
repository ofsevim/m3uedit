"""
M3U Parser Test Module
M3U parser modülü için unit testler.
"""

import unittest
import io
from utils.m3u_parser import M3UParser


class TestM3UParser(unittest.TestCase):
    """M3U parser test sınıfı"""
    
    def setUp(self):
        """Test öncesi kurulum"""
        self.parser = M3UParser()
        
        # Örnek M3U içeriği
        self.sample_m3u = """#EXTM3U
#EXTINF:-1 group-title="TR SPOR",TR SPOR 1
http://example.com/trspor1.m3u8
#EXTINF:-1 group-title="TR SPOR",TR SPOR 2
http://example.com/trspor2.m3u8
#EXTINF:-1 group-title="INTERNATIONAL",BBC World
http://example.com/bbc.m3u8
"""
    
    def test_parse_m3u_lines(self):
        """M3U satırlarını parse etme testi"""
        iterator = io.StringIO(self.sample_m3u)
        channels = self.parser.parse_m3u_lines(iterator)
        
        self.assertEqual(len(channels), 3)
        self.assertEqual(channels[0]["Grup"], "TR SPOR")
        self.assertEqual(channels[0]["Kanal Adı"], "TR SPOR 1")
        self.assertEqual(channels[0]["URL"], "http://example.com/trspor1.m3u8")
    
    def test_filter_channels_tr_only(self):
        """TR kanallarını filtreleme testi"""
        iterator = io.StringIO(self.sample_m3u)
        channels = self.parser.parse_m3u_lines(iterator)
        filtered = self.parser.filter_channels(channels, only_tr=True)
        
        self.assertEqual(len(filtered), 2)  # Sadece TR SPOR kanalları
        self.assertTrue(all("TR" in ch["Grup"] for ch in filtered))
    
    def test_filter_channels_all(self):
        """Tüm kanalları filtreleme testi"""
        iterator = io.StringIO(self.sample_m3u)
        channels = self.parser.parse_m3u_lines(iterator)
        filtered = self.parser.filter_channels(channels, only_tr=False)
        
        self.assertEqual(len(filtered), 3)  # Tüm kanallar
    
    def test_convert_to_m3u(self):
        """M3U formatına dönüştürme testi"""
        channels = [
            {
                "Grup": "TEST",
                "Kanal Adı": "Test Channel",
                "URL": "http://example.com/test.m3u8",
                "LogoURL": "http://example.com/logo.png"
            }
        ]
        
        m3u_output = self.parser.convert_to_m3u(channels)
        
        self.assertIn("#EXTM3U", m3u_output)
        self.assertIn("group-title=\"TEST\"", m3u_output)
        self.assertIn("Test Channel", m3u_output)
        self.assertIn("http://example.com/test.m3u8", m3u_output)
    
    def test_find_duplicates(self):
        """Tekrarlı kanalları bulma testi"""
        channels = [
            {"Grup": "A", "Kanal Adı": "Channel 1", "URL": "url1"},
            {"Grup": "A", "Kanal Adı": "Channel 1", "URL": "url1"},  # Duplicate
            {"Grup": "B", "Kanal Adı": "Channel 2", "URL": "url2"},
        ]
        
        duplicates = self.parser.find_duplicates(channels)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0], 1)  # İkinci kanal duplicate
    
    def test_remove_duplicates(self):
        """Tekrarlı kanalları kaldırma testi"""
        channels = [
            {"Grup": "A", "Kanal Adı": "Channel 1", "URL": "url1"},
            {"Grup": "A", "Kanal Adı": "Channel 1", "URL": "url1"},  # Duplicate
            {"Grup": "B", "Kanal Adı": "Channel 2", "URL": "url2"},
        ]
        
        unique = self.parser.remove_duplicates(channels)
        self.assertEqual(len(unique), 2)  # Duplicate kaldırıldı
    
    def test_parse_with_logo(self):
        """Logo bilgisi içeren M3U parse testi"""
        m3u_with_logo = """#EXTM3U
#EXTINF:-1 tvg-logo="http://example.com/logo1.png" group-title="TR",Channel 1
http://example.com/ch1.m3u8
"""
        
        iterator = io.StringIO(m3u_with_logo)
        channels = self.parser.parse_m3u_lines(iterator)
        
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0]["LogoURL"], "http://example.com/logo1.png")
    
    def test_parse_with_tvg_info(self):
        """TVG bilgileri içeren M3U parse testi"""
        m3u_with_tvg = """#EXTM3U
#EXTINF:-1 tvg-id="trt1.tr" tvg-name="TRT 1" tvg-logo="trt1.png" group-title="TR",TRT 1
http://example.com/trt1.m3u8
"""
        
        iterator = io.StringIO(m3u_with_tvg)
        channels = self.parser.parse_m3u_lines(iterator)
        
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0]["TvgID"], "trt1.tr")
        self.assertEqual(channels[0]["TvgName"], "TRT 1")
        self.assertEqual(channels[0]["LogoURL"], "trt1.png")


class TestHelperFunctions(unittest.TestCase):
    """Yardımcı fonksiyon testleri"""
    
    def test_parse_m3u_lines_helper(self):
        """Yardımcı parse fonksiyonu testi"""
        from utils.m3u_parser import parse_m3u_lines
        
        m3u_content = """#EXTM3U
#EXTINF:-1 group-title="TEST",Test Channel
http://example.com/test.m3u8
"""
        
        iterator = io.StringIO(m3u_content)
        channels = parse_m3u_lines(iterator)
        
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0]["Kanal Adı"], "Test Channel")
    
    def test_filter_channels_helper(self):
        """Yardımcı filtre fonksiyonu testi"""
        from utils.m3u_parser import filter_channels
        
        channels = [
            {"Grup": "TR SPOR", "Kanal Adı": "Channel 1", "URL": "url1"},
            {"Grup": "INTERNATIONAL", "Kanal Adı": "Channel 2", "URL": "url2"},
        ]
        
        filtered = filter_channels(channels, only_tr=True)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["Grup"], "TR SPOR")


if __name__ == '__main__':
    unittest.main()