"""
M3U Parser Module
IPTV M3U playlist dosyalarını parse etmek için yardımcı fonksiyonlar.
"""

import re
import urllib.request
import urllib.error
import ssl
from typing import List, Dict, Iterator, Optional
import io


class M3UParser:
    """M3U playlist parser sınıfı"""
    
    def __init__(self, config=None):
        """
        M3U parser başlatıcı
        
        Args:
            config: Yapılandırma sözlüğü (opsiyonel)
        """
        self.config = config or {}
        
        # TR kanal tespiti için regex pattern
        self.tr_pattern = re.compile(
            r'(\b|_|\[|\(|\|)(TR|TURK|TÜRK|TURKIYE|TÜRKİYE|YERLI|ULUSAL|ISTANBUL)(\b|_|\]|\)|\||:)', 
            re.IGNORECASE
        )
        
        # Varsayılan ayarlar
        self.default_settings = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'timeout': 30,
            'disable_ssl_verify': True
        }
        
        # Config'den ayarları al
        self.settings = {**self.default_settings, **self.config}
    
    def parse_m3u_lines(self, iterator: Iterator) -> List[Dict]:
        """
        M3U formatındaki kanalları parse eder ve liste olarak döner.
        
        Args:
            iterator: Satır satır okunabilen iterator (dosya veya HTTP response)
            
        Returns:
            List[Dict]: Parse edilmiş kanal listesi
        """
        channels = []
        current_info = None

        for line in iterator:
            # Gelen satır byte ise decode et, string ise olduğu gibi al
            if isinstance(line, bytes):
                try:
                    line = line.decode('utf-8', errors='ignore').strip()
                except:
                    continue
            else:
                line = line.strip()

            if not line:
                continue
                
            if line.startswith("#EXTINF"):
                info = {
                    "Grup": "Genel", 
                    "Kanal Adı": "Bilinmeyen", 
                    "URL": "", 
                    "LogoURL": "",
                    "TvgID": "",
                    "TvgName": ""
                }
                
                # TVG logos may be provided as tvg-logo="<url>"
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                if logo_match:
                    info["LogoURL"] = logo_match.group(1)
                
                # TVG ID
                tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
                if tvg_id_match:
                    info["TvgID"] = tvg_id_match.group(1)
                
                # TVG Name
                tvg_name_match = re.search(r'tvg-name="([^"]*)"', line)
                if tvg_name_match:
                    info["TvgName"] = tvg_name_match.group(1)
                
                # Group title
                grp = re.search(r'group-title="([^"]*)"', line)
                if grp:
                    info["Grup"] = grp.group(1)
                
                # Kanal adı (EXTINF satırının son kısmı)
                parts = line.split(",")
                if len(parts) > 1:
                    info["Kanal Adı"] = parts[-1].strip()
                
                current_info = info
                
            elif line and not line.startswith("#"):
                if current_info:
                    current_info["URL"] = line
                    channels.append(current_info)
                    current_info = None

        return channels
    
    def filter_channels(self, channels: List[Dict], only_tr: bool = False) -> List[Dict]:
        """
        Kanalları filtreler.
        
        Args:
            channels: Kanal listesi
            only_tr: Sadece Türk kanallarını filtrele
            
        Returns:
            List[Dict]: Filtrelenmiş kanal listesi
        """
        if not only_tr:
            return channels
            
        filtered = []
        
        for ch in channels:
            if self.tr_pattern.search(ch["Grup"]):
                filtered.append(ch)
                
        return filtered
    
    def download_from_url(self, url: str) -> List[Dict]:
        """
        URL'den M3U playlist indirir ve parse eder.
        
        Args:
            url: M3U playlist URL'si
            
        Returns:
            List[Dict]: Parse edilmiş kanal listesi
            
        Raises:
            urllib.error.HTTPError: HTTP hatası durumunda
            urllib.error.URLError: Bağlantı hatası durumunda
            TimeoutError: Zaman aşımı durumunda
        """
        headers = {'User-Agent': self.settings['user_agent']}
        req = urllib.request.Request(url, headers=headers)
        
        # SSL sertifika hatalarını yok saymak için context
        ctx = None
        if self.settings.get('disable_ssl_verify', True):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=self.settings['timeout'], context=ctx) as response:
            return self.parse_m3u_lines(response)
    
    def load_from_file(self, file_content: bytes) -> List[Dict]:
        """
        Dosya içeriğinden M3U playlist parse eder.
        
        Args:
            file_content: M3U dosya içeriği (bytes)
            
        Returns:
            List[Dict]: Parse edilmiş kanal listesi
        """
        stringio = io.StringIO(file_content.decode("utf-8", errors='ignore'))
        return self.parse_m3u_lines(stringio)
    
    def convert_to_m3u(self, channels: List[Dict]) -> str:
        """
        Kanal listesini M3U formatına çevirir.
        
        Args:
            channels: Kanal listesi
            
        Returns:
            str: M3U formatında string
        """
        content = "#EXTM3U\n"
        for channel in channels:
            # EXTINF satırını oluştur
            extinf_line = f'#EXTINF:-1'
            
            # TVG bilgilerini ekle
            if channel.get("TvgID"):
                extinf_line += f' tvg-id="{channel["TvgID"]}"'
            if channel.get("TvgName"):
                extinf_line += f' tvg-name="{channel["TvgName"]}"'
            if channel.get("LogoURL"):
                extinf_line += f' tvg-logo="{channel["LogoURL"]}"'
            
            # Group title ve kanal adı
            extinf_line += f' group-title="{channel["Grup"]}",{channel["Kanal Adı"]}'
            
            content += extinf_line + "\n"
            content += channel["URL"] + "\n"
        
        return content
    
    def find_duplicates(self, channels: List[Dict]) -> List[int]:
        """
        Tekrarlı kanalları bulur.
        
        Args:
            channels: Kanal listesi
            
        Returns:
            List[int]: Tekrarlı kanal indeksleri
        """
        seen = set()
        duplicates = []
        
        for i, channel in enumerate(channels):
            key = (channel["Grup"], channel["Kanal Adı"], channel["URL"])
            if key in seen:
                duplicates.append(i)
            else:
                seen.add(key)
        
        return duplicates
    
    def remove_duplicates(self, channels: List[Dict]) -> List[Dict]:
        """
        Tekrarlı kanalları kaldırır.
        
        Args:
            channels: Kanal listesi
            
        Returns:
            List[Dict]: Tekrarlardan arındırılmış kanal listesi
        """
        seen = set()
        unique_channels = []
        
        for channel in channels:
            key = (channel["Grup"], channel["Kanal Adı"], channel["URL"])
            if key not in seen:
                seen.add(key)
                unique_channels.append(channel)
        
        return unique_channels


# Kolay kullanım için yardımcı fonksiyonlar
def parse_m3u_lines(iterator: Iterator) -> List[Dict]:
    """Kolay kullanım için parse fonksiyonu"""
    parser = M3UParser()
    return parser.parse_m3u_lines(iterator)


def filter_channels(channels: List[Dict], only_tr: bool = False) -> List[Dict]:
    """Kolay kullanım için filtre fonksiyonu"""
    parser = M3UParser()
    return parser.filter_channels(channels, only_tr)


def convert_df_to_m3u(df) -> str:
    """DataFrame'i M3U formatına çevirir"""
    parser = M3UParser()
    channels = df.to_dict('records')
    return parser.convert_to_m3u(channels)