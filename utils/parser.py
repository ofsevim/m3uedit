import re
import pandas as pd
import concurrent.futures
import urllib.request
import urllib.error
import socket
import ssl
import time
import logging
import threading
from typing import Iterable, List, Dict, Callable, Optional

logger = logging.getLogger(__name__)

# Türk kanallar için regex pattern
TR_PATTERN = re.compile(
    r"(\b|_|\[|\(|\|)(TR|TURK|TÜRK|TURKIYE|TÜRKİYE|YERLI|ULUSAL|ISTANBUL)(\b|_|\]|\)|\||:)",
    re.IGNORECASE,
)

# SSL - sertifika hatalarını atla
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

def parse_m3u_lines(iterator: Iterable) -> List[Dict[str, str]]:
    """M3U satırlarını parse eder ve kanal listesi döndürür.
    
    Args:
        iterator: M3U dosyasının satırları (str veya bytes)
        
    Returns:
        Kanal bilgilerini içeren dict listesi
    """
    channels: List[Dict[str, str]] = []
    current_info: Optional[Dict[str, str]] = None
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

def filter_channels(
    channels: List[Dict[str, str]],
    only_tr: bool = False,
    keyword: str = "",
    group_filter: str = ""
) -> List[Dict[str, str]]:
    """Kanal listesini verilen kriterlere göre filtreler.
    
    Args:
        channels: Filtrelenecek kanal listesi
        only_tr: Sadece Türk kanallarını filtrele
        keyword: Kanal adı veya grup adında aranacak kelime
        group_filter: Sadece belirtilen gruptaki kanalları göster
        
    Returns:
        Filtrelenmiş kanal listesi
    """
    result: List[Dict[str, str]] = channels
    if only_tr:
        result = [ch for ch in result if TR_PATTERN.search(ch.get("Grup", "") + " " + ch.get("Kanal Adı", ""))]
    if keyword:
        kw = keyword.lower()
        result = [ch for ch in result if kw in ch.get("Kanal Adı", "").lower() or kw in ch.get("Grup", "").lower()]
    if group_filter:
        result = [ch for ch in result if ch.get("Grup", "") == group_filter]
    return result

def _check_single_url(url: str, timeout: float = 3.0) -> str:
    """
    Tek URL'yi mümkün olan en hızlı şekilde kontrol eder.
    
    Strateji:
      1) HEAD isteği (body indirmez, çok hızlı)
      2) HEAD 405 ise → kısa GET (sadece ilk 1KB)
      3) Sonuca göre durum emoji döndür
    """
    if not url or not url.startswith(("http://", "https://")):
        return "❌ Geçersiz"

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; HealthCheck/1.0)",
        "Connection": "close",      # Bağlantıyı hemen kapat
        "Accept": "*/*",
    }

    # ── 1. HEAD İsteği (en hızlı) ──
    try:
        req = urllib.request.Request(url, headers=headers, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
            code = resp.status
            content_type = (resp.getheader("Content-Type") or "").lower()

            if code == 200:
                if "mpegurl" in content_type or "video" in content_type or "octet-stream" in content_type:
                    return "✅ Aktif"
                elif "text/html" in content_type:
                    return "⚠️ Web Sayfası"
                else:
                    return "✅ Aktif"
            elif code in (301, 302, 303, 307, 308):
                return "🔀 Yönlendirme"
            elif code == 403:
                return "🔒 Yasaklı"
            elif code == 404:
                return "❌ Bulunamadı"
            else:
                return f"⚠️ HTTP {code}"

    except urllib.error.HTTPError as e:
        if e.code == 405:
            # HEAD desteklenmiyor → kısa GET dene
            pass
        elif e.code == 403:
            return "🔒 Yasaklı"
        elif e.code == 404:
            return "❌ Bulunamadı"
        elif e.code == 401:
            return "🔑 Yetki Gerekli"
        else:
            return f"⚠️ HTTP {e.code}"
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError):
        # HEAD başarısız → GET deneyelim
        pass
    except Exception:
        pass

    # ── 2. Kısa GET İsteği (sadece ilk 1KB) ──
    try:
        headers["Range"] = "bytes=0-1023"  # Sadece ilk 1KB
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
            _ = resp.read(1024)  # Sadece 1KB oku
            code = resp.status
            if code in (200, 206):
                return "✅ Aktif"
            else:
                return f"⚠️ HTTP {code}"

    except urllib.error.HTTPError as e:
        if e.code == 403:
            return "🔒 CORS/Yasaklı"
        return f"⚠️ HTTP {e.code}"
    except (socket.timeout, TimeoutError):
        return "⏱️ Zaman Aşımı"
    except (urllib.error.URLError, OSError) as e:
        reason = str(getattr(e, 'reason', e))
        if "ssl" in reason.lower() or "certificate" in reason.lower():
            return "🔒 SSL Hatası"
        return "❌ Bağlantı Hatası"
    except Exception:
        return "❌ Hata"

def batch_check_health(
    urls: List[str],
    max_workers: int = 50,
    timeout: float = 3.0,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[str]:
    """
    URL listesini paralel olarak kontrol eder.
    """
    total = len(urls)
    if total == 0:
        return []

    # Worker sayısını URL sayısına göre ayarla
    workers = min(max_workers, total)
    results = ["❔ Bekliyor"] * total
    completed = 0
    progress_lock = threading.Lock()

    def check_with_index(args):
        nonlocal completed
        idx, url = args
        result = _check_single_url(url, timeout=timeout)
        if progress_callback:
            try:
                with progress_lock:
                    completed += 1
                    current_completed = completed
                progress_callback(current_completed, total)
            except Exception:
                pass
        else:
            with progress_lock:
                completed += 1
        return idx, result

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(check_with_index, (i, url)): i 
            for i, url in enumerate(urls)
        }

        for future in concurrent.futures.as_completed(futures):
            try:
                idx, result = future.result(timeout=timeout + 5)
                results[idx] = result
            except concurrent.futures.TimeoutError:
                idx = futures[future]
                results[idx] = "⏱️ Zaman Aşımı"
            except Exception as e:
                idx = futures[future]
                results[idx] = "❌ Hata"

    return results

def convert_df_to_m3u(df: pd.DataFrame) -> str:
    """Pandas DataFrame'i M3U formatına dönüştürür.
    
    Args:
        df: Kanal bilgilerini içeren DataFrame
        
    Returns:
        M3U formatında string
    """
    lines: List[str] = ["#EXTM3U"]
    for _, row in df.iterrows():
        logo = row.get("LogoURL", "")
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        lines.append(f'#EXTINF:-1{logo_attr} group-title="{row["Grup"]}",{row["Kanal Adı"]}')
        lines.append(str(row["URL"]))
    return "\n".join(lines) + "\n"
