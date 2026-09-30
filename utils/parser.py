import concurrent.futures
import logging
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Dict, Iterable, List, Optional

import pandas as pd

from utils import network
from utils.security import validate_url

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

_ATTR_RE = re.compile(r"([\w-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s]+))")


def detect_type(url: str) -> str:
    path = urllib.parse.urlsplit(str(url)).path.lower()
    if path.endswith(".mpd"):
        return "DASH"
    if path.endswith(".ts"):
        return "MPEG-TS"
    if path.endswith((".mp4", ".webm")):
        return "Diğer"
    if path.endswith(".m3u8") or "/live/" in path:
        return "HLS"
    return "Diğer"


def parse_m3u_lines(iterator: Iterable) -> List[Dict]:
    """Preserve playlist headers, attributes and per-channel player directives."""
    channels, current, header = [], None, "#EXTM3U"
    global_directives = []
    for raw in iterator:
        line = raw.decode("utf-8-sig", errors="replace") if isinstance(raw, bytes) else str(raw)
        line = line.strip().lstrip("\ufeff")
        if not line:
            continue
        if line.startswith("#EXTM3U"):
            header = line
        elif line.startswith("#EXTINF:"):
            quoted = None
            delimiter = len(line)
            for i, char in enumerate(line):
                if char in ('"', "'"):
                    if quoted == char:
                        quoted = None
                    elif quoted is None:
                        quoted = char
                elif char == "," and quoted is None:
                    delimiter = i
                    break
            metadata, name = line[:delimiter], line[delimiter + 1 :]
            attributes = {
                m.group(1): next((v for v in m.groups()[1:] if v is not None), "")
                for m in _ATTR_RE.finditer(metadata)
            }
            duration = (
                metadata[len("#EXTINF:") :].split()[0]
                if metadata[len("#EXTINF:") :].strip()
                else "-1"
            )
            current = {
                "Grup": attributes.get("group-title", "Genel"),
                "Kanal Adı": name.strip() or attributes.get("tvg-name", "Bilinmeyen"),
                "URL": "",
                "LogoURL": attributes.get("tvg-logo", ""),
                "_Attributes": attributes,
                "_Directives": [],
                "_Duration": duration,
                "_Header": header,
                "_GlobalDirectives": tuple(global_directives),
            }
        elif line.startswith("#"):
            if current is not None:
                current["_Directives"].append(line)
            elif channels:
                channels[-1].setdefault("_TrailingDirectives", []).append(line)
            elif not channels:
                global_directives.append(line)
        elif current is not None:
            current["URL"] = line
            current["Tür"] = detect_type(line)
            channels.append(current)
            current = None
    return channels


def filter_channels(
    channels: List[Dict[str, str]], only_tr: bool = False, keyword: str = "", group_filter: str = ""
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
        result = [
            ch
            for ch in result
            if TR_PATTERN.search(ch.get("Grup", "") + " " + ch.get("Kanal Adı", ""))
        ]
    if keyword:
        kw = keyword.lower()
        result = [
            ch
            for ch in result
            if kw in ch.get("Kanal Adı", "").lower() or kw in ch.get("Grup", "").lower()
        ]
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
      2) HEAD 405 ise → Range GET (yanıt başlıklarından sonra bağlantıyı kapat)
      3) Sonuca göre durum emoji ve metin döndür (403/451 durumunda VPN uyarısı)
    """
    try:
        validate_url(url)
    except ValueError:
        return "❌ Geçersiz"

    # 🌐 İYİLEŞTİRME: Tutarlı ve tarayıcı benzeri User-Agent kullanılarak engellemeler önlenir
    req_headers = {
        "User-Agent": user_agent or USER_AGENT,
        "Connection": "close",  # Bağlantıyı hemen kapat
        "Accept": "*/*",
    }
    if headers:
        req_headers.update(headers)

    def _open(req):
        if proxy_url:
            return network.open_url(req, timeout=timeout, proxy_url=proxy_url)
        return network.open_url(req, timeout=timeout)

    # ── 1. HEAD İsteği (en hızlı) ──
    try:
        req = urllib.request.Request(url, headers=req_headers, method="HEAD")
        with _open(req) as resp:
            code = resp.status
            content_type = (resp.getheader("Content-Type") or "").lower()

            if code in (200, 206):
                if (
                    "mpegurl" in content_type
                    or "video" in content_type
                    or "octet-stream" in content_type
                ):
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

    except ValueError:
        return "❌ Geçersiz"
    except urllib.error.HTTPError as e:
        e.close()
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
            code = resp.status
            if code in (200, 206):
                return "✅ Aktif"
            elif code in (403, 451):
                return "🌍 VPN Gerekebilir"
            else:
                return f"⚠️ HTTP {code}"

    except ValueError:
        return "❌ Geçersiz"
    except urllib.error.HTTPError as e:
        e.close()
        if e.code in (403, 451):
            return "🌍 VPN Gerekebilir"
        return f"⚠️ HTTP {e.code}"
    except (socket.timeout, TimeoutError):
        return "⏱️ Zaman Aşımı"
    except (urllib.error.URLError, OSError) as e:
        reason = str(getattr(e, "reason", e))
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

    workers = min(max(1, max_workers), total)
    results = ["❔ Bekliyor"] * total
    pending_inputs = iter(enumerate(urls))
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:

        def submit_next():
            try:
                idx, url = next(pending_inputs)
            except StopIteration:
                return None
            return executor.submit(
                _check_single_url,
                url,
                timeout=timeout,
                user_agent=user_agent,
                proxy_url=proxy_url,
                headers=headers,
            ), idx

        pending = dict(submit_next() for _ in range(workers))
        while pending:
            done, _ = concurrent.futures.wait(
                pending, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                idx = pending.pop(future)
                try:
                    results[idx] = future.result()
                except Exception:
                    results[idx] = "❌ Hata"
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
                next_job = submit_next()
                if next_job:
                    pending[next_job[0]] = next_job[1]
    return results


def _clean_m3u_field(value: object, *, is_attr: bool = False) -> str:
    """M3U satırını bozabilecek karakterleri temizler.

    Satır sonları (CR/LF) bir kanalın iki satıra bölünmesine; attribute
    değerlerindeki çift tırnak ise ``group-title="..."`` gibi alanların
    kırılmasına yol açar. Bu karakterleri güvenli karşılıklarıyla değiştiririz.
    """
    if value is None or (not isinstance(value, (dict, list, tuple)) and pd.isna(value)):
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    if is_attr:
        text = text.replace('"', "'")
    return text


def _convert_m3u(df: pd.DataFrame, proxy_base_url: str | None = None) -> str:
    first = df.iloc[0] if not df.empty else {}
    header = _clean_m3u_field(first.get("_Header", "")) or df.attrs.get("m3u_header", "#EXTM3U")
    lines = [header if header.startswith("#EXTM3U") else "#EXTM3U"]
    globals_ = first.get("_GlobalDirectives", ())
    if isinstance(globals_, (list, tuple)):
        lines.extend(_clean_m3u_field(value) for value in globals_ if str(value).startswith("#"))
    for values in df.itertuples(index=False, name=None):
        row = dict(zip(df.columns, values))
        attributes = row.get("_Attributes", {})
        attributes = dict(attributes) if isinstance(attributes, dict) else {}
        attributes["group-title"] = row.get("Grup", "Genel")
        logo = _clean_m3u_field(row.get("LogoURL", ""), is_attr=True)
        if logo:
            attributes["tvg-logo"] = logo
        else:
            attributes.pop("tvg-logo", None)
        attrs = "".join(
            f' {key}="{_clean_m3u_field(value, is_attr=True)}"'
            for key, value in attributes.items()
            if re.fullmatch(r"[\w-]+", str(key))
        )
        duration = str(row.get("_Duration", "-1"))
        if not re.fullmatch(r"-?\d+(?:\.\d+)?", duration):
            duration = "-1"
        name = _clean_m3u_field(row.get("Kanal Adı", ""))
        lines.append(f"#EXTINF:{duration}{attrs},{name}")
        directives = row.get("_Directives", [])
        if isinstance(directives, (list, tuple)):
            lines.extend(_clean_m3u_field(d) for d in directives if str(d).startswith("#"))
        url = _clean_m3u_field(row.get("URL", ""))
        if proxy_base_url:
            separator = "&" if "?" in proxy_base_url else "?"
            url = f"{proxy_base_url}{separator}url={urllib.parse.quote(url, safe='')}"
        lines.append(url)
        trailing = row.get("_TrailingDirectives", [])
        if isinstance(trailing, (list, tuple)):
            lines.extend(_clean_m3u_field(d) for d in trailing if str(d).startswith("#"))
    return "\n".join(lines) + "\n"


def convert_df_to_m3u(df: pd.DataFrame) -> str:
    return _convert_m3u(df)


def convert_df_to_proxied_m3u(df: pd.DataFrame, proxy_base_url: str) -> str:
    return _convert_m3u(df, proxy_base_url)


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
