import re
import pandas as pd
from typing import Iterable, List, Dict

# Türk kanallar için regex pattern
TR_PATTERN = re.compile(
    r"(\b|_|\[|\(|\|)(TR|TURK|TÜRK|TURKIYE|TÜRKİYE|YERLI|ULUSAL|ISTANBUL)(\b|_|\]|\)|\||:)",
    re.IGNORECASE,
)

def parse_m3u_lines(iterator: Iterable) -> List[Dict]:
    """M3U satırlarını parse eder ve kanal listesi döndürür."""
    channels = []
    current_info = None
    for line in iterator:
        if isinstance(line, bytes):
            try:
                line = line.decode("utf-8", errors="ignore").strip()
            except Exception:
                continue
        else:
            line = line.strip()
            
        if not line:
            continue
            
        if line.startswith("#EXTINF"):
            info = {"Grup": "Genel", "Kanal Adı": "Bilinmeyen", "URL": "", "LogoURL": ""}
            
            # Logo tespiti
            logo = re.search(r'tvg-logo="([^"]*)"', line)
            if logo:
                info["LogoURL"] = logo.group(1)
                
            # Grup tespiti
            grp = re.search(r'group-title="([^"]*)"', line)
            if grp:
                info["Grup"] = grp.group(1)
                
            # Kanal adı tespiti
            parts = line.split(",")
            if len(parts) > 1:
                info["Kanal Adı"] = parts[-1].strip()
                
            current_info = info
        elif not line.startswith("#"):
            if current_info:
                current_info["URL"] = line
                lower = line.lower()
                
                # Tür tespiti
                if ".m3u8" in lower or "/live/" in lower:
                    current_info["Tür"] = "HLS"
                elif ".mpd" in lower:
                    current_info["Tür"] = "DASH"
                else:
                    current_info["Tür"] = "Diğer"
                    
                channels.append(current_info)
                current_info = None
    return channels

def filter_channels(channels: List[Dict], only_tr: bool = False, keyword: str = "", group_filter: str = "") -> List[Dict]:
    """Kanal listesini filtreler."""
    result = channels
    if only_tr:
        result = [ch for ch in result if TR_PATTERN.search(ch.get("Grup", "") + " " + ch.get("Kanal Adı", ""))]
    if keyword:
        kw = keyword.lower()
        result = [ch for ch in result if kw in ch.get("Kanal Adı", "").lower() or kw in ch.get("Grup", "").lower()]
    if group_filter:
        result = [ch for ch in result if ch.get("Grup", "") == group_filter]
    return result

import concurrent.futures
import urllib.request
import ssl

def check_channel_health(url: str, timeout: int = 3) -> bool:
    """Tek bir kanalın sağlığını kontrol eder (HTTP HEAD/GET)."""
    if not url or not url.startswith("http"):
        return False
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    # 1) Önce HEAD isteği (Hızlı)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    # 2) Fallback: GET isteği (Bazı sunucular HEAD desteklemez)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="GET")
        # Sadece ilk birkaç byte'ı okumak yeterli
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status == 200
    except Exception:
        return False

def batch_check_health(urls: List[str], max_workers: int = 10, timeout: int = 5) -> List[bool]:
    """Birden fazla kanalın sağlığını paralel olarak kontrol eder."""
    results = [False] * len(urls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {executor.submit(check_channel_health, url, timeout): i for i, url in enumerate(urls)}
        for future in concurrent.futures.as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception:
                results[index] = False
    return results

def convert_df_to_m3u(df: pd.DataFrame) -> str:
    """Pandas DataFrame'i M3U formatına dönüştürür."""
    lines = ["#EXTM3U"]
    for _, row in df.iterrows():
        logo = row.get("LogoURL", "")
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        lines.append(f'#EXTINF:-1{logo_attr} group-title="{row["Grup"]}",{row["Kanal Adı"]}')
        lines.append(str(row["URL"]))
    return "\n".join(lines) + "\n"
