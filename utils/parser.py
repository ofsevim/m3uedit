import re
import json
import pandas as pd
import concurrent.futures
import urllib.request
import urllib.error
import urllib.parse
import socket
import ssl
import time
import logging
import threading
from typing import Iterable, List, Dict, Callable, Optional

logger = logging.getLogger(__name__)

# Config'den tarayıcı User-Agent'ını çek, hata durumunda güvenli bir varsayılan kullan
try:
    from utils.config import USER_AGENT
except ImportError:
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

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

def _check_single_url(
    url: str,
    timeout: float = 3.0,
    user_agent: Optional[str] = None,
    proxy_url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> str:
    """
    Tek URL'yi mümkün olan en hızlı şekilde kontrol eder.
    
    Strateji:
      1) HEAD isteği (body indirmez, çok hızlı)
      2) HEAD 405 ise → kısa GET (sadece ilk 1KB)
      3) Sonuca göre durum emoji ve metin döndür (403/451 durumunda VPN uyarısı)
    """
    if not url or not url.startswith(("http://", "https://")):
        return "❌ Geçersiz"

    # 🌐 İYİLEŞTİRME: Tutarlı ve tarayıcı benzeri User-Agent kullanılarak engellemeler önlenir
    req_headers = {
        "User-Agent": user_agent or USER_AGENT,
        "Connection": "close",      # Bağlantıyı hemen kapat
        "Accept": "*/*",
    }
    if headers:
        req_headers.update(headers)

    def _open(req):
        if proxy_url:
            p_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            s_handler = urllib.request.HTTPSHandler(context=_ssl_ctx)
            opener = urllib.request.build_opener(p_handler, s_handler)
            return opener.open(req, timeout=timeout)
        return urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx)

    # ── 1. HEAD İsteği (en hızlı) ──
    try:
        req = urllib.request.Request(url, headers=req_headers, method="HEAD")
        with _open(req) as resp:
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
            elif code in (403, 451):
                return "🌍 VPN Gerekebilir"
            elif code == 404:
                return "❌ Bulunamadı"
            elif code == 401:
                return "🔑 Yetki Gerekli"
            else:
                return f"⚠️ HTTP {code}"

    except urllib.error.HTTPError as e:
        if e.code == 405:
            # HEAD desteklenmiyor → kısa GET dene
            pass
        elif e.code in (403, 451):
            return "🌍 VPN Gerekebilir"
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
        get_headers = dict(req_headers)
        get_headers["Range"] = "bytes=0-1023"  # Sadece ilk 1KB
        req = urllib.request.Request(url, headers=get_headers, method="GET")
        with _open(req) as resp:
            _ = resp.read(1024)  # Sadece 1KB oku
            code = resp.status
            if code in (200, 206):
                return "✅ Aktif"
            elif code in (403, 451):
                return "🌍 VPN Gerekebilir"
            else:
                return f"⚠️ HTTP {code}"

    except urllib.error.HTTPError as e:
        if e.code in (403, 451):
            return "🌍 VPN Gerekebilir"
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
    user_agent: Optional[str] = None,
    proxy_url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
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
        result = _check_single_url(
            url,
            timeout=timeout,
            user_agent=user_agent,
            proxy_url=proxy_url,
            headers=headers,
        )
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

def _clean_m3u_field(value: object, *, is_attr: bool = False) -> str:
    """M3U satırını bozabilecek karakterleri temizler.

    Satır sonları (CR/LF) bir kanalın iki satıra bölünmesine; attribute
    değerlerindeki çift tırnak ise ``group-title="..."`` gibi alanların
    kırılmasına yol açar. Bu karakterleri güvenli karşılıklarıyla değiştiririz.
    """
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    if is_attr:
        text = text.replace('"', "'")
    return text


def convert_df_to_m3u(df: pd.DataFrame) -> str:
    """Pandas DataFrame'i M3U formatına dönüştürür.

    Args:
        df: Kanal bilgilerini içeren DataFrame

    Returns:
        M3U formatında string
    """
    lines: List[str] = ["#EXTM3U"]
    for _, row in df.iterrows():
        logo = _clean_m3u_field(row.get("LogoURL", ""), is_attr=True)
        group = _clean_m3u_field(row.get("Grup", "Genel"), is_attr=True)
        name = _clean_m3u_field(row.get("Kanal Adı", ""))
        url = _clean_m3u_field(row.get("URL", ""))
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        lines.append(f'#EXTINF:-1{logo_attr} group-title="{group}",{name}')
        lines.append(url)
    return "\n".join(lines) + "\n"


def convert_df_to_proxied_m3u(df: pd.DataFrame, proxy_base_url: str) -> str:
    """Pandas DataFrame'i akış URL'leri yerel proxy üzerinden yönlendirilecek şekilde M3U formatına dönüştürür.
    
    Smart TV veya VPN olmayan harici cihazlar için uygundur.
    """
    lines: List[str] = ["#EXTM3U"]
    for _, row in df.iterrows():
        logo = _clean_m3u_field(row.get("LogoURL", ""), is_attr=True)
        group = _clean_m3u_field(row.get("Grup", "Genel"), is_attr=True)
        name = _clean_m3u_field(row.get("Kanal Adı", ""))
        url = _clean_m3u_field(row.get("URL", ""))
        proxied_url = f"{proxy_base_url}?url={urllib.parse.quote(url, safe='')}"
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        lines.append(f'#EXTINF:-1{logo_attr} group-title="{group}",{name}')
        lines.append(proxied_url)
    return "\n".join(lines) + "\n"


def convert_df_to_csv(df: pd.DataFrame) -> str:
    """Kanal listesini CSV formatına dönüştürür."""
    cols = [c for c in ["Kanal Adı", "Grup", "URL", "Tür", "LogoURL", "Durum"] if c in df.columns]
    target_df = df[cols] if cols else df
    return target_df.to_csv(index=False, encoding="utf-8")


def convert_df_to_json(df: pd.DataFrame) -> str:
    """Kanal listesini JSON formatına dönüştürür."""
    cols = [c for c in ["Kanal Adı", "Grup", "URL", "Tür", "LogoURL", "Durum"] if c in df.columns]
    target_df = df[cols] if cols else df
    return target_df.to_json(orient="records", indent=2, force_ascii=False)


def convert_df_to_txt(df: pd.DataFrame) -> str:
    """Sadece URL listesini TXT formatında döndürür."""
    if "URL" in df.columns:
        return "\n".join(df["URL"].dropna().astype(str).tolist()) + "\n"
    return ""

