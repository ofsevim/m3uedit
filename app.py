import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import urllib.request
import urllib.error
import ssl
import re
import io
import json
import sys
import os
import time
import uuid
import hashlib
import logging
import concurrent.futures
from datetime import datetime
from typing import Iterable, List, Dict, Optional
from collections import Counter

# --- LOG YAPILANDIRMASI ---
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )
logger = logging.getLogger(__name__)

# --- SAYFA AYARLARI (İLK STREAMLIT KOMUTU OLMALI) ---
st.set_page_config(
    page_title="M3U Editör Pro (Web)",
    layout="wide",
    page_icon="📺",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/yourusername/m3uedit",
        "Report a bug": "https://github.com/yourusername/m3uedit/issues",
        "About": "# M3U Editör Pro v2.0\nIPTV playlist yönetim aracı",
    },
)

# --- MODÜL YOLLARI ---
# Root app.py: current_dir = proje kökü
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from utils.visitor_counter import VisitorCounter
    from utils.config import (
        REQUEST_TIMEOUT, DISABLE_SSL_VERIFY, USER_AGENT,
        TR_KEYWORDS, DEFAULT_TR_FILTER, TABLE_HEIGHT,
        DEFAULT_EXPORT_FILENAME, EXPORT_FILE_EXTENSION,
        DEBUG_MODE, CACHE_TTL, MAX_FILE_SIZE_MB,
    )
except ImportError:
    logger.warning("utils modülü bulunamadı, fallback değerler kullanılıyor.")

    class VisitorCounter:
        def __init__(self, *a, **kw): pass
        def increment_visit(self, *a, **kw): return 0
        def get_stats(self):
            return {"total_visits": 0, "unique_visitors": 0, "first_visit": "N/A", "last_visit": "N/A"}

    REQUEST_TIMEOUT = 30
    DISABLE_SSL_VERIFY = True
    USER_AGENT = "Mozilla/5.0"
    TR_KEYWORDS = ["TR", "TURK", "TÜRK", "TURKIYE", "TÜRKİYE", "YERLI", "ULUSAL", "ISTANBUL"]
    DEFAULT_TR_FILTER = True
    TABLE_HEIGHT = 600
    DEFAULT_EXPORT_FILENAME = "iptv_listesi"
    EXPORT_FILE_EXTENSION = ".m3u"
    DEBUG_MODE = False
    CACHE_TTL = 300
    MAX_FILE_SIZE_MB = 50


# =====================================================================
# YARDIMCI FONKSİYONLAR
# =====================================================================

# Streamlit Cloud read-only filesystem güvenliği: yazılabilir dizin tespit et
def _get_writable_dir() -> str:
    """Yazılabilir bir dizin döndürür (Cloud uyumlu)."""
    for d in ["/tmp", os.environ.get("TMPDIR", ""), current_dir]:
        if d and os.path.isdir(d):
            try:
                test_file = os.path.join(d, ".write_test")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                return d
            except OSError:
                continue
    return current_dir


_WRITABLE_DIR = _get_writable_dir()
HISTORY_FILE = os.path.join(_WRITABLE_DIR, "history.json")
FAVORITES_FILE = os.path.join(_WRITABLE_DIR, "favorites.json")
BOOKMARKS_FILE = os.path.join(_WRITABLE_DIR, "bookmarks.json")

TR_PATTERN = re.compile(
    r"(\b|_|\[|\(|\|)(TR|TURK|TÜRK|TURKIYE|TÜRKİYE|YERLI|ULUSAL|ISTANBUL)(\b|_|\]|\)|\||:)",
    re.IGNORECASE,
)


def _create_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _safe_contains(series: pd.Series, term: str) -> pd.Series:
    return series.astype(str).str.contains(term, case=False, na=False)


def _get_selected_mask(df: pd.DataFrame) -> pd.Series:
    """DataFrame'den 'Seç' kolonunu güvenli şekilde boolean mask olarak döndürür."""
    if "Seç" in df.columns:
        return df["Seç"].fillna(False).astype(bool)
    return pd.Series(False, index=df.index)


# --- JSON DOSYA İŞLEMLERİ (yazma hataları sessizce yutulur) ---
def _load_json_file(filepath: str) -> list:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def _save_json_file(filepath: str, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def add_history(entry: dict):
    hist = _load_json_file(HISTORY_FILE)
    entry["timestamp"] = datetime.now().isoformat()
    hist.append(entry)
    if len(hist) > 100:
        hist = hist[-100:]
    _save_json_file(HISTORY_FILE, hist)


def load_favorites() -> list:
    return _load_json_file(FAVORITES_FILE)


def save_favorites(favs: list):
    _save_json_file(FAVORITES_FILE, favs)


def add_favorite(channel: dict):
    favs = load_favorites()
    key = f"{channel.get('Kanal Adı', '')}|{channel.get('URL', '')}"
    if not any(f"{f.get('Kanal Adı', '')}|{f.get('URL', '')}" == key for f in favs):
        channel["added_at"] = datetime.now().isoformat()
        favs.append(channel)
        save_favorites(favs)
        return True
    return False


def remove_favorite(channel_name: str, url: str):
    favs = load_favorites()
    favs = [f for f in favs if not (f.get("Kanal Adı") == channel_name and f.get("URL") == url)]
    save_favorites(favs)


def load_bookmarks() -> list:
    return _load_json_file(BOOKMARKS_FILE)


def save_bookmarks(bm: list):
    _save_json_file(BOOKMARKS_FILE, bm)


# --- CSS ---
def _load_css():
    """CSS dosyasını yükle — birden fazla olası yolu dene."""
    candidates = [
        os.path.join(current_dir, "static", "styles.css"),
        os.path.join(os.getcwd(), "static", "styles.css"),
    ]
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
                return
        except OSError:
            continue

_load_css()


# =====================================================================
# PARSE & DÖNÜŞÜM FONKSİYONLARI
# =====================================================================

def parse_m3u_lines(iterator: Iterable) -> List[Dict]:
    """M3U satırlarını parse ederek kanal bilgilerini çıkarır."""
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

            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            if logo_match:
                info["LogoURL"] = logo_match.group(1)

            tvg_id = re.search(r'tvg-id="([^"]*)"', line)
            if tvg_id:
                info["TVG-ID"] = tvg_id.group(1)

            tvg_name = re.search(r'tvg-name="([^"]*)"', line)
            if tvg_name:
                info["TVG-Name"] = tvg_name.group(1)

            tvg_lang = re.search(r'tvg-language="([^"]*)"', line)
            if tvg_lang:
                info["Dil"] = tvg_lang.group(1)

            tvg_country = re.search(r'tvg-country="([^"]*)"', line)
            if tvg_country:
                info["Ülke"] = tvg_country.group(1)

            grp = re.search(r'group-title="([^"]*)"', line)
            if grp:
                info["Grup"] = grp.group(1)

            parts = line.split(",")
            if len(parts) > 1:
                info["Kanal Adı"] = parts[-1].strip()

            current_info = info

        elif not line.startswith("#"):
            if current_info:
                current_info["URL"] = line
                lower_url = line.lower()
                if ".m3u8" in lower_url or "/live/" in lower_url:
                    current_info["Tür"] = "HLS"
                elif ".mpd" in lower_url:
                    current_info["Tür"] = "DASH"
                elif ".ts" in lower_url:
                    current_info["Tür"] = "MPEG-TS"
                else:
                    current_info["Tür"] = "Diğer"
                channels.append(current_info)
                current_info = None

    return channels


def filter_channels(channels: List[Dict], only_tr: bool = False,
                    keyword: str = "", group_filter: str = "") -> List[Dict]:
    result = channels
    if only_tr:
        result = [ch for ch in result if TR_PATTERN.search(ch.get("Grup", ""))]
    if keyword:
        kw = keyword.lower()
        result = [ch for ch in result if kw in ch.get("Kanal Adı", "").lower()
                  or kw in ch.get("Grup", "").lower()]
    if group_filter:
        result = [ch for ch in result if ch.get("Grup", "") == group_filter]
    return result


def convert_df_to_m3u(df: pd.DataFrame) -> str:
    lines = ["#EXTM3U"]
    for _, row in df.iterrows():
        logo = row.get("LogoURL", "")
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        tvg_id = row.get("TVG-ID", "")
        tvg_attr = f' tvg-id="{tvg_id}"' if tvg_id else ""
        lang = row.get("Dil", "")
        lang_attr = f' tvg-language="{lang}"' if lang else ""
        lines.append(
            f'#EXTINF:-1{tvg_attr}{logo_attr}{lang_attr} group-title="{row["Grup"]}",{row["Kanal Adı"]}'
        )
        lines.append(str(row["URL"]))
    return "\n".join(lines) + "\n"


def convert_df_to_csv(df: pd.DataFrame) -> str:
    export_cols = [c for c in ["Grup", "Kanal Adı", "URL", "LogoURL", "Dil", "Ülke", "Tür"] if c in df.columns]
    return df[export_cols].to_csv(index=False)


def convert_df_to_json(df: pd.DataFrame) -> str:
    export_cols = [c for c in ["Grup", "Kanal Adı", "URL", "LogoURL", "Dil", "Ülke", "Tür"] if c in df.columns]
    return df[export_cols].to_json(orient="records", force_ascii=False, indent=2)


def merge_playlists(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    merged = pd.concat([df1, df2], ignore_index=True)
    merged = merged.drop_duplicates(subset=["Kanal Adı", "URL"], keep="first")
    return merged.reset_index(drop=True)


def get_playlist_stats(df: pd.DataFrame) -> dict:
    stats = {
        "total": len(df),
        "groups": df["Grup"].nunique() if "Grup" in df.columns else 0,
        "duplicates": int(df.duplicated(subset=["Kanal Adı", "URL"]).sum()) if not df.empty else 0,
        "empty_urls": int((df["URL"].astype(str).str.strip() == "").sum()) if "URL" in df.columns else 0,
        "hls_count": 0, "dash_count": 0,
        "group_distribution": {}, "type_distribution": {},
    }
    if "Tür" in df.columns:
        stats["hls_count"] = int((df["Tür"] == "HLS").sum())
        stats["dash_count"] = int((df["Tür"] == "DASH").sum())
        stats["type_distribution"] = df["Tür"].value_counts().to_dict()
    if "Grup" in df.columns:
        stats["group_distribution"] = df["Grup"].value_counts().head(20).to_dict()
    return stats


def check_single_url(url_str: str, timeout: int = 5) -> str:
    if not url_str or url_str.strip() == "":
        return "Boş URL"
    try:
        req = urllib.request.Request(url_str, headers={"User-Agent": USER_AGENT})
        ctx = _create_ssl_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            code = getattr(resp, "status", 200)
            return "✅ OK" if int(code) < 400 else f"⚠️ {code}"
    except urllib.error.HTTPError as e:
        return f"❌ HTTP {e.code}"
    except Exception:
        return "❌ HATA"


def check_urls_parallel(urls: List[str], max_workers: int = 10, timeout: int = 5) -> List[str]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_single_url, u, timeout): i for i, u in enumerate(urls)}
        results = ["⏳"] * len(urls)
        for future in concurrent.futures.as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = "❌ HATA"
    return results


# =====================================================================
# VIDEO OYNATICI
# =====================================================================

def render_live_player(stream_url: str, height: int = 420) -> str:
    url = (stream_url or "").replace("'", "\\'").replace('"', '\\"')
    h = str(height)
    return f"""
    <div style='width:100%;height:{h}px;background:#000;border-radius:12px;overflow:hidden;position:relative;'>
        <video id='m3u_player' controls autoplay playsinline
               style='width:100%;height:100%;object-fit:contain;'></video>
        <div id='error_msg' style='display:none;color:#fff;padding:20px;text-align:center;
             position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);'>
            <p style='font-size:1.2rem;'>⚠️ Video yüklenemedi</p>
            <p style='font-size:0.85rem;color:#aaa;'>URL geçerli olmayabilir veya CORS hatası olabilir.</p>
        </div>
        <div id='loading_indicator' style='position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
             color:#fff;font-size:1.5rem;'>⏳ Yükleniyor...</div>
    </div>
    <script src='https://cdn.jsdelivr.net/npm/hls.js@latest'></script>
    <script>
    (function(){{
        var video = document.getElementById('m3u_player');
        var errorDiv = document.getElementById('error_msg');
        var loadDiv = document.getElementById('loading_indicator');
        var url = '{url}';
        function showError(){{ errorDiv.style.display='block'; video.style.display='none'; loadDiv.style.display='none'; }}
        function hideLoading(){{ loadDiv.style.display='none'; }}
        if (!url) {{ showError(); return; }}
        if (Hls.isSupported()) {{
            var hls = new Hls({{enableWorker:true,lowLatencyMode:true,backBufferLength:90}});
            hls.loadSource(url); hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, function(){{ hideLoading(); video.play().catch(function(){{}}); }});
            hls.on(Hls.Events.ERROR, function(event,data){{
                if(data.fatal){{
                    if(data.type===Hls.ErrorTypes.NETWORK_ERROR){{ hls.startLoad(); }}
                    else {{ showError(); }}
                }}
            }});
        }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
            video.src = url;
            video.addEventListener('loadedmetadata', function(){{ hideLoading(); video.play().catch(function(){{}}); }});
            video.addEventListener('error', function(){{ showError(); }});
        }} else {{ showError(); }}
        setTimeout(hideLoading, 10000);
    }})();
    </script>
    """


# =====================================================================
# SESSION STATE
# =====================================================================

if "visitor_counter" not in st.session_state:
    st.session_state.visitor_counter = VisitorCounter()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.visitor_counter.increment_visit(st.session_state.session_id)

if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame()

if "play_channel" not in st.session_state:
    st.session_state.play_channel = None

if "undo_stack" not in st.session_state:
    st.session_state.undo_stack = []


def push_undo():
    if not st.session_state.data.empty:
        st.session_state.undo_stack.append(st.session_state.data.copy())
        if len(st.session_state.undo_stack) > 20:
            st.session_state.undo_stack.pop(0)


def pop_undo():
    if st.session_state.undo_stack:
        st.session_state.data = st.session_state.undo_stack.pop()
        return True
    return False


def _prepare_new_data(raw_channels: List[Dict]) -> pd.DataFrame:
    new_data = pd.DataFrame(raw_channels)
    if new_data.empty:
        return new_data
    for col, default in [("Seç", False), ("Favori", False), ("LogoURL", ""),
                         ("Durum", ""), ("Tür", ""), ("Dil", ""), ("Ülke", "")]:
        if col not in new_data.columns:
            new_data[col] = default
    priority = ["Seç", "Favori", "Grup", "Kanal Adı", "URL", "Tür", "Dil", "Ülke", "LogoURL", "Durum"]
    ordered = [c for c in priority if c in new_data.columns]
    remaining = [c for c in new_data.columns if c not in ordered]
    new_data = new_data[ordered + remaining]
    return new_data


# =====================================================================
# SIDEBAR
# =====================================================================

with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:1rem 0;'>"
        "<h1 style='margin:0;font-size:2.5rem;'>📺</h1>"
        "<h2 style='margin:0.5rem 0 0 0;font-size:1.4rem;'>M3U Editör Pro</h2>"
        "<p style='margin:0.25rem 0 0 0;color:#888;font-size:0.85rem;'>v2.0 — IPTV Yönetim Aracı</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    mode = st.radio("📥 Yükleme Yöntemi", ["🌐 Linkten Yükle", "📂 Dosya Yükle", "📋 Yapıştır (Metin)"])

    selected_groups = []
    if not st.session_state.data.empty:
        st.markdown("#### ⚙️ Sıralama & Filtre")
        sort_cols = [c for c in ["Grup", "Kanal Adı", "URL", "Tür", "Dil"] if c in st.session_state.data.columns]
        sort_by = st.selectbox("Sırala", sort_cols, index=0)
        sort_dir = st.radio("Yön", ["A → Z", "Z → A"], index=0, horizontal=True)

        sort_key = f"{sort_by}_{sort_dir}"
        if st.session_state.get("last_sort") != sort_key:
            st.session_state.data = st.session_state.data.sort_values(
                by=sort_by, ascending=(sort_dir == "A → Z")
            ).reset_index(drop=True)
            st.session_state.last_sort = sort_key

        try:
            group_options = sorted(st.session_state.data["Grup"].astype(str).dropna().unique())
        except Exception:
            group_options = []
        if group_options:
            selected_groups = st.multiselect("Grupları filtrele", group_options, default=group_options)

    new_data = None

    if mode == "🌐 Linkten Yükle":
        bookmarks = load_bookmarks()
        if bookmarks:
            bm_names = ["— Yer İmi Seç —"] + [b.get("name", b.get("url", "")) for b in bookmarks]
            bm_choice = st.selectbox("📌 Yer İmleri", bm_names, key="bm_select")
            if bm_choice != "— Yer İmi Seç —":
                bm_item = next((b for b in bookmarks if b.get("name", b.get("url", "")) == bm_choice), None)
                if bm_item:
                    st.session_state["_bm_url"] = bm_item.get("url", "")

        url = st.text_input("M3U Linki Yapıştır:", value=st.session_state.get("_bm_url", ""))
        col_tr, col_bm = st.columns(2)
        only_tr = col_tr.checkbox("🇹🇷 TR Filtresi", value=DEFAULT_TR_FILTER)

        if col_bm.button("📌 Kaydet", help="URL'yi yer imlerine ekle"):
            if url:
                bms = load_bookmarks()
                if not any(b.get("url") == url for b in bms):
                    bms.append({"name": url[:50], "url": url, "added": datetime.now().isoformat()})
                    save_bookmarks(bms)
                    st.success("Yer imi kaydedildi.")
                    st.rerun()
                else:
                    st.info("Zaten yer imlerinde.")

        if st.button("🚀 Listeyi Çek ve Tara", use_container_width=True, type="primary"):
            if url:
                try:
                    with st.spinner("Link indiriliyor ve taranıyor..."):
                        headers = {"User-Agent": USER_AGENT}
                        req = urllib.request.Request(url, headers=headers)
                        ctx = _create_ssl_context()
                        start_time = time.time()

                        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx) as response:
                            raw_channels = parse_m3u_lines(response)
                            final_channels = filter_channels(raw_channels, only_tr)
                            elapsed = round(time.time() - start_time, 2)
                            new_data = _prepare_new_data(final_channels)
                            duplicates = (
                                new_data.duplicated(subset=["Kanal Adı", "URL"]).sum()
                                if not new_data.empty else 0
                            )
                            if not final_channels:
                                st.warning("⚠️ Kanal bulunamadı veya format hatalı.")
                            else:
                                st.success(f"✅ {len(final_channels)} kanal bulundu ({elapsed}s)")
                                add_history({"type": "load", "count": len(final_channels), "url": url})
                            if duplicates:
                                st.info(f"🔄 {int(duplicates)} tekrarlı kanal.")
                except urllib.error.HTTPError as e:
                    st.error(f"🚫 HTTP Hatası: {e.code} - {e.reason}")
                except urllib.error.URLError as e:
                    st.error(f"🔌 Bağlantı Hatası: {e.reason}")
                except TimeoutError:
                    st.error(f"⏱️ Zaman Aşımı ({REQUEST_TIMEOUT}s)")
                except Exception as e:
                    logger.error("Kanal yükleme hatası", exc_info=True)
                    st.error(f"❌ Hata: {e}")
            else:
                st.warning("Lütfen bir link girin.")

    elif mode == "📂 Dosya Yükle":
        uploaded_files = st.file_uploader("M3U Dosyası Seç", type=["m3u", "m3u8"], accept_multiple_files=True)
        if uploaded_files:
            all_channels = []
            for uf in uploaded_files:
                stringio = io.StringIO(uf.getvalue().decode("utf-8", errors="ignore"))
                all_channels.extend(parse_m3u_lines(stringio))
            new_data = _prepare_new_data(all_channels)
            st.success(f"📂 {len(uploaded_files)} dosyadan {len(all_channels)} kanal yüklendi.")

    elif mode == "📋 Yapıştır (Metin)":
        pasted = st.text_area("M3U içeriğini yapıştırın:", height=200,
                              placeholder="#EXTM3U\n#EXTINF:-1,Kanal\nhttp://...")
        if st.button("📋 Yapıştırılanı Yükle", use_container_width=True):
            if pasted.strip():
                raw_channels = parse_m3u_lines(pasted.strip().splitlines())
                new_data = _prepare_new_data(raw_channels)
                if raw_channels:
                    st.success(f"✅ {len(raw_channels)} kanal yüklendi.")
                else:
                    st.warning("Geçerli M3U verisi bulunamadı.")

    if new_data is not None and not new_data.empty:
        push_undo()
        st.session_state.data = new_data

    st.markdown("---")

    # --- TOPLU İŞLEMLER ---
    if not st.session_state.data.empty:
        st.markdown("#### 🛠️ Toplu İşlemler")
        bc1, bc2 = st.columns(2)
        if bc1.button("☑️ Tümünü Seç", use_container_width=True):
            st.session_state.data["Seç"] = True
            st.rerun()
        if bc2.button("⬜ Seçimi Kaldır", use_container_width=True):
            st.session_state.data["Seç"] = False
            st.rerun()

        bc3, bc4 = st.columns(2)
        if bc3.button("🗑️ Çiftleri Temizle", use_container_width=True):
            push_undo()
            before = len(st.session_state.data)
            st.session_state.data = st.session_state.data.drop_duplicates(
                subset=["Kanal Adı", "URL"], keep="first"
            ).reset_index(drop=True)
            after = len(st.session_state.data)
            st.success(f"{before - after} çift kanal silindi.")
            st.rerun()
        if bc4.button("↩️ Geri Al", use_container_width=True):
            if pop_undo():
                st.success("Geri alındı.")
                st.rerun()
            else:
                st.info("Geri alınacak işlem yok.")

        if st.button("🗑️ Seçilenleri Sil", use_container_width=True):
            mask = _get_selected_mask(st.session_state.data)
            count = mask.sum()
            if count > 0:
                push_undo()
                st.session_state.data = st.session_state.data[~mask].reset_index(drop=True)
                st.success(f"{count} kanal silindi.")
                st.rerun()
            else:
                st.info("Silinecek seçili kanal yok.")

        if st.button("🧹 Boş URL'leri Temizle", use_container_width=True):
            push_undo()
            before = len(st.session_state.data)
            st.session_state.data = st.session_state.data[
                st.session_state.data["URL"].astype(str).str.strip() != ""
            ].reset_index(drop=True)
            st.success(f"{before - len(st.session_state.data)} boş URL silindi.")
            st.rerun()

    st.markdown("---")

    # --- EXPORT ---
    if not st.session_state.data.empty:
        st.markdown("#### 💾 Dışa Aktar")
        sel_mask = _get_selected_mask(st.session_state.data)
        count_selected = int(sel_mask.sum())

        if count_selected > 0:
            st.success(f"✅ {count_selected} kanal seçildi.")
            download_df = st.session_state.data[sel_mask]
            suffix = "_secilenler"
        else:
            st.info("ℹ️ Seçim yok → tüm liste")
            download_df = st.session_state.data
            suffix = "_tum_liste"

        m3u_output = convert_df_to_m3u(download_df)
        st.download_button(
            label=f"📥 M3U ({len(download_df)})", data=m3u_output,
            file_name=f"{DEFAULT_EXPORT_FILENAME}{suffix}{EXPORT_FILE_EXTENSION}",
            mime="text/plain", type="primary", use_container_width=True,
        )
        st.download_button(
            label=f"📥 JSON ({len(download_df)})", data=convert_df_to_json(download_df),
            file_name=f"{DEFAULT_EXPORT_FILENAME}{suffix}.json",
            mime="application/json", use_container_width=True,
        )
        st.download_button(
            label=f"📥 CSV ({len(download_df)})", data=convert_df_to_csv(download_df),
            file_name=f"{DEFAULT_EXPORT_FILENAME}{suffix}.csv",
            mime="text/csv", use_container_width=True,
        )


# =====================================================================
# ANA EKRAN — SEKMELER
# =====================================================================

tab_editor, tab_stats, tab_favorites, tab_history, tab_tools = st.tabs(
    ["📝 Düzenleyici", "📊 İstatistikler", "⭐ Favoriler", "📜 Geçmiş", "🔧 Araçlar"]
)

# --- SEKME 1: DÜZENLEYICI ---
with tab_editor:
    if not st.session_state.data.empty:
        pstats = get_playlist_stats(st.session_state.data)
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("📺 Toplam", pstats["total"])
        mc2.metric("✅ Seçilen", int(_get_selected_mask(st.session_state.data).sum()))
        mc3.metric("📁 Grup", pstats["groups"])
        mc4.metric("🔄 Çift", pstats["duplicates"])
        mc5.metric("⚠️ Boş URL", pstats["empty_urls"])

        search_col1, search_col2 = st.columns([3, 1])
        with search_col1:
            search_term = st.text_input("🔍 Ara (Grup, Kanal Adı, URL):", "", key="main_search")
        with search_col2:
            search_field = st.selectbox("Arama Alanı", ["Tümü", "Grup", "Kanal Adı", "URL"], key="search_field")

        df_display = st.session_state.data.copy()
        if selected_groups:
            df_display = df_display[df_display["Grup"].isin(selected_groups)]
        if search_term:
            if search_field == "Tümü":
                df_display = df_display[
                    _safe_contains(df_display["Grup"], search_term)
                    | _safe_contains(df_display["Kanal Adı"], search_term)
                    | _safe_contains(df_display["URL"], search_term)
                ]
            else:
                df_display = df_display[_safe_contains(df_display[search_field], search_term)]

        st.caption(f"Gösterilen: {len(df_display)} / {len(st.session_state.data)} kanal")

        # Canlı Oynatıcı
        st.markdown("### 🎬 Canlı Oynatıcı")
        col_play1, col_play2, col_play3 = st.columns([3, 1, 1])
        with col_play1:
            play_options = df_display["Kanal Adı"].tolist() if not df_display.empty else []
            play_channel_name = st.selectbox(
                "Oynatılacak Kanal", options=play_options,
                index=None, placeholder="Kanal seçin...", key="play_select",
            )
        with col_play2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("▶ OYNAT", use_container_width=True, key="play_btn", type="primary"):
                if play_channel_name:
                    row = df_display[df_display["Kanal Adı"] == play_channel_name]
                    if not row.empty:
                        st.session_state.play_channel = {
                            "name": play_channel_name,
                            "url": row.iloc[0]["URL"],
                            "logo": row.iloc[0].get("LogoURL", ""),
                            "group": row.iloc[0].get("Grup", ""),
                        }
                        st.rerun()
        with col_play3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⭐ Favorile", use_container_width=True, key="fav_btn"):
                if play_channel_name:
                    row = df_display[df_display["Kanal Adı"] == play_channel_name]
                    if not row.empty:
                        ch = row.iloc[0].to_dict()
                        if add_favorite(ch):
                            st.success(f"⭐ {play_channel_name} favorilere eklendi.")
                        else:
                            st.info("Zaten favorilerde.")

        if st.session_state.play_channel:
            pc = st.session_state.play_channel
            pcol1, pcol2 = st.columns([1, 4])
            with pcol1:
                if pc.get("logo"):
                    try:
                        st.image(pc["logo"], width=120)
                    except Exception:
                        pass
                st.markdown(f"**Grup:** {pc.get('group', 'N/A')}")
            with pcol2:
                st.markdown(f"### ▶ {pc['name']}")
                components.html(render_live_player(pc["url"], height=380), height=420)

            if st.button("⏹ Durdur", use_container_width=True):
                st.session_state.play_channel = None
                st.rerun()
            st.markdown("---")

        st.caption("Kanalları düzenlemek için tablodaki hücrelere tıklayın.")
        display_cols = [c for c in ["Seç", "Favori", "Grup", "Kanal Adı", "URL", "Tür", "Durum"]
                        if c in df_display.columns]

        edited_df = st.data_editor(
            df_display[display_cols] if display_cols else df_display,
            num_rows="dynamic", use_container_width=True, hide_index=True,
            height=TABLE_HEIGHT, key="editor",
            column_config={
                "Seç": st.column_config.CheckboxColumn("✅", default=False, width="small"),
                "Favori": st.column_config.CheckboxColumn("⭐", default=False, width="small"),
                "URL": st.column_config.LinkColumn("URL", width="large"),
                "Tür": st.column_config.TextColumn("Tür", width="small"),
                "Durum": st.column_config.TextColumn("Durum", width="small"),
            },
        )

        if edited_df is not None:
            ref = df_display[display_cols] if display_cols else df_display
            if not edited_df.equals(ref):
                st.session_state.data.update(edited_df)
    else:
        st.markdown(
            "<div style='text-align:center;padding:80px 20px;'>"
            "<div style='font-size:4rem;margin-bottom:1rem;'>📺</div>"
            "<h2 style='color:#ccc;'>M3U Editör Pro'ya Hoş Geldiniz</h2>"
            "<p style='color:#888;font-size:1.1rem;max-width:500px;margin:1rem auto;'>"
            "Sol menüden bir M3U linki yapıştırın, dosya yükleyin veya metin yapıştırarak başlayın.</p>"
            "</div>",
            unsafe_allow_html=True,
        )


# --- SEKME 2: İSTATİSTİKLER ---
with tab_stats:
    if not st.session_state.data.empty:
        st.markdown("### 📊 Playlist Analizi")
        pstats = get_playlist_stats(st.session_state.data)

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("📺 Toplam", pstats["total"])
        s2.metric("📁 Grup", pstats["groups"])
        s3.metric("🔄 Tekrarlı", pstats["duplicates"])
        s4.metric("📡 HLS", pstats["hls_count"])

        if pstats["group_distribution"]:
            st.markdown("#### 📁 Grup Dağılımı (İlk 20)")
            group_df = pd.DataFrame(list(pstats["group_distribution"].items()), columns=["Grup", "Kanal Sayısı"])
            st.bar_chart(group_df.set_index("Grup"), height=400)

        if pstats["type_distribution"]:
            st.markdown("#### 📡 Akış Türü Dağılımı")
            type_df = pd.DataFrame(list(pstats["type_distribution"].items()), columns=["Tür", "Sayı"])
            tc1, tc2 = st.columns([1, 2])
            with tc1:
                st.dataframe(type_df, hide_index=True, use_container_width=True)
            with tc2:
                st.bar_chart(type_df.set_index("Tür"), height=300)

        if "Dil" in st.session_state.data.columns:
            lang_counts = st.session_state.data["Dil"].dropna().astype(str)
            lang_counts = lang_counts[lang_counts != ""].value_counts().head(15)
            if not lang_counts.empty:
                st.markdown("#### 🌍 Dil Dağılımı")
                st.bar_chart(pd.DataFrame({"Dil": lang_counts.index, "Sayı": lang_counts.values}).set_index("Dil"), height=300)

        st.markdown("#### 🔍 URL Sağlık Kontrolü")
        hc1, hc2 = st.columns([1, 3])
        with hc1:
            max_check = st.number_input("Max kanal", min_value=1, max_value=500, value=50)
            workers = st.number_input("Paralel thread", min_value=1, max_value=20, value=10)
        with hc2:
            if st.button("🚀 Sağlık Kontrolü Başlat", use_container_width=True, type="primary"):
                df = st.session_state.data.copy()
                urls = df["URL"].astype(str).tolist()[:max_check]
                with st.spinner(f"{len(urls)} URL kontrol ediliyor..."):
                    results = check_urls_parallel(urls, max_workers=workers)
                df.loc[df.index[:len(results)], "Durum"] = results
                st.session_state.data = df
                ok_count = sum(1 for r in results if "OK" in r)
                err_count = sum(1 for r in results if "HATA" in r or "HTTP" in r)
                st.success(f"✅ {ok_count} aktif, ❌ {err_count} hatalı")
                st.rerun()

        if "Durum" in st.session_state.data.columns:
            durum_counts = st.session_state.data["Durum"].astype(str).value_counts()
            durum_counts = durum_counts[durum_counts.index != ""]
            if not durum_counts.empty:
                st.markdown("#### 📋 Durum Özeti")
                st.dataframe(pd.DataFrame({"Durum": durum_counts.index, "Sayı": durum_counts.values}),
                             hide_index=True, use_container_width=True)
    else:
        st.info("📊 İstatistikleri görmek için önce bir playlist yükleyin.")


# --- SEKME 3: FAVORİLER ---
with tab_favorites:
    st.markdown("### ⭐ Favori Kanallarım")
    favs = load_favorites()

    if favs:
        fav_df = pd.DataFrame(favs)
        display_fav_cols = [c for c in ["Kanal Adı", "Grup", "URL", "added_at"] if c in fav_df.columns]
        st.dataframe(fav_df[display_fav_cols], hide_index=True, use_container_width=True, height=400)

        fav_names = fav_df["Kanal Adı"].tolist() if "Kanal Adı" in fav_df.columns else []
        fc1, fc2, fc3 = st.columns([3, 1, 1])
        with fc1:
            fav_play = st.selectbox("Favori Kanal", fav_names, index=None,
                                    placeholder="Kanal seçin...", key="fav_play_select")
        with fc2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("▶ Oynat", key="fav_play_btn", use_container_width=True):
                if fav_play:
                    fav_row = fav_df[fav_df["Kanal Adı"] == fav_play].iloc[0]
                    st.session_state.play_channel = {
                        "name": fav_play, "url": fav_row.get("URL", ""),
                        "logo": fav_row.get("LogoURL", ""), "group": fav_row.get("Grup", ""),
                    }
                    st.rerun()
        with fc3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️ Sil", key="fav_del_btn", use_container_width=True):
                if fav_play:
                    fav_row = fav_df[fav_df["Kanal Adı"] == fav_play].iloc[0]
                    remove_favorite(fav_play, fav_row.get("URL", ""))
                    st.success(f"🗑️ {fav_play} silindi.")
                    st.rerun()

        if st.button("🗑️ Tüm Favorileri Temizle", use_container_width=True):
            save_favorites([])
            st.success("Favoriler temizlendi.")
            st.rerun()
    else:
        st.markdown(
            "<div style='text-align:center;padding:60px;'>"
            "<div style='font-size:3rem;'>⭐</div>"
            "<p style='color:#888;margin-top:1rem;'>Henüz favori kanal yok.</p>"
            "</div>", unsafe_allow_html=True,
        )


# --- SEKME 4: GEÇMİŞ ---
with tab_history:
    st.markdown("### 📜 İşlem Geçmişi")
    hist = _load_json_file(HISTORY_FILE)

    if hist:
        hist_df = pd.DataFrame(hist)
        if "timestamp" in hist_df.columns:
            hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"], errors="coerce")
            hist_df = hist_df.sort_values("timestamp", ascending=False)
        display_hist_cols = [c for c in ["type", "count", "url", "timestamp"] if c in hist_df.columns]
        st.dataframe(hist_df[display_hist_cols].head(50), hide_index=True, use_container_width=True, height=400)

        if st.button("🗑️ Geçmişi Temizle", use_container_width=True):
            _save_json_file(HISTORY_FILE, [])
            st.success("Geçmiş temizlendi.")
            st.rerun()
    else:
        st.info("📜 Henüz işlem geçmişi yok.")


# --- SEKME 5: ARAÇLAR ---
with tab_tools:
    st.markdown("### 🔧 Gelişmiş Araçlar")

    tool_choice = st.selectbox("Araç Seçin", [
        "🔀 Playlist Birleştirici",
        "🔍 Playlist Karşılaştırıcı",
        "✏️ Toplu Grup Adı Değiştir",
        "🔗 URL Bul & Değiştir",
        "📌 Yer İmi Yöneticisi",
        "🧹 Gelişmiş Temizlik",
    ], key="tool_select")

    if tool_choice == "🔀 Playlist Birleştirici":
        st.info("Mevcut listeye yeni bir M3U ekleyin. Çiftler otomatik kaldırılır.")
        merge_file = st.file_uploader("M3U Dosyası", type=["m3u", "m3u8"], key="merge_upload")
        if merge_file and st.button("🔀 Birleştir", type="primary"):
            if not st.session_state.data.empty:
                push_undo()
                stringio = io.StringIO(merge_file.getvalue().decode("utf-8", errors="ignore"))
                new_channels = parse_m3u_lines(stringio)
                new_df = _prepare_new_data(new_channels)
                before = len(st.session_state.data)
                st.session_state.data = merge_playlists(st.session_state.data, new_df)
                st.success(f"✅ {len(st.session_state.data) - before} yeni kanal eklendi.")
                st.rerun()
            else:
                st.warning("Önce bir playlist yükleyin.")

    elif tool_choice == "🔍 Playlist Karşılaştırıcı":
        compare_file = st.file_uploader("Karşılaştırılacak M3U", type=["m3u", "m3u8"], key="compare_upload")
        if compare_file and st.button("🔍 Karşılaştır", type="primary"):
            if not st.session_state.data.empty:
                stringio = io.StringIO(compare_file.getvalue().decode("utf-8", errors="ignore"))
                compare_channels = parse_m3u_lines(stringio)
                compare_df = _prepare_new_data(compare_channels)

                current_keys = set(st.session_state.data["Kanal Adı"].astype(str) + "|" + st.session_state.data["URL"].astype(str))
                compare_keys = set(compare_df["Kanal Adı"].astype(str) + "|" + compare_df["URL"].astype(str))

                common = current_keys & compare_keys
                only_current = current_keys - compare_keys
                only_compare = compare_keys - current_keys

                cc1, cc2, cc3 = st.columns(3)
                cc1.metric("🟢 Ortak", len(common))
                cc2.metric("🔵 Sadece Mevcut", len(only_current))
                cc3.metric("🟠 Sadece Yeni", len(only_compare))

                if only_compare:
                    st.markdown("##### 🟠 Yeni Dosyada Olup Mevcut Listede Olmayan")
                    new_only = compare_df[
                        (compare_df["Kanal Adı"].astype(str) + "|" + compare_df["URL"].astype(str)).isin(only_compare)
                    ]
                    st.dataframe(new_only[["Kanal Adı", "Grup", "URL"]].head(50), hide_index=True)
            else:
                st.warning("Önce bir playlist yükleyin.")

    elif tool_choice == "✏️ Toplu Grup Adı Değiştir":
        if not st.session_state.data.empty:
            groups = sorted(st.session_state.data["Grup"].astype(str).unique())
            old_group = st.selectbox("Eski Grup Adı", groups, key="old_group")
            new_group = st.text_input("Yeni Grup Adı", key="new_group")
            if st.button("✏️ Değiştir", type="primary") and new_group:
                push_undo()
                count = int((st.session_state.data["Grup"] == old_group).sum())
                st.session_state.data.loc[st.session_state.data["Grup"] == old_group, "Grup"] = new_group
                st.success(f"✅ {count} kanal güncellendi: '{old_group}' → '{new_group}'")
                st.rerun()
        else:
            st.info("Önce bir playlist yükleyin.")

    elif tool_choice == "🔗 URL Bul & Değiştir":
        if not st.session_state.data.empty:
            find_str = st.text_input("Bulunacak metin:", key="url_find")
            replace_str = st.text_input("Değiştirilecek metin:", key="url_replace")
            if st.button("🔗 Değiştir", type="primary") and find_str:
                push_undo()
                mask = st.session_state.data["URL"].astype(str).str.contains(find_str, na=False)
                count = int(mask.sum())
                st.session_state.data.loc[mask, "URL"] = (
                    st.session_state.data.loc[mask, "URL"].astype(str).str.replace(find_str, replace_str, regex=False)
                )
                st.success(f"✅ {count} URL güncellendi.")
                st.rerun()
        else:
            st.info("Önce bir playlist yükleyin.")

    elif tool_choice == "📌 Yer İmi Yöneticisi":
        bms = load_bookmarks()
        if bms:
            st.dataframe(pd.DataFrame(bms), hide_index=True, use_container_width=True)
            del_bm = st.selectbox("Silinecek", [b.get("name", b.get("url", "")) for b in bms], key="del_bm")
            if st.button("🗑️ Sil"):
                bms = [b for b in bms if b.get("name", b.get("url", "")) != del_bm]
                save_bookmarks(bms)
                st.success("Silindi.")
                st.rerun()
        else:
            st.info("Henüz yer imi yok.")

        st.markdown("##### ➕ Yeni Yer İmi")
        bm_name = st.text_input("İsim:", key="new_bm_name")
        bm_url = st.text_input("URL:", key="new_bm_url")
        if st.button("➕ Ekle", key="add_bm_btn") and bm_url:
            bms = load_bookmarks()
            bms.append({"name": bm_name or bm_url[:50], "url": bm_url, "added": datetime.now().isoformat()})
            save_bookmarks(bms)
            st.success("Eklendi.")
            st.rerun()

    elif tool_choice == "🧹 Gelişmiş Temizlik":
        if not st.session_state.data.empty:
            if st.button("🗑️ Hatalı kanalları sil (Durum=HATA)", use_container_width=True):
                if "Durum" in st.session_state.data.columns:
                    push_undo()
                    mask = st.session_state.data["Durum"].astype(str).str.contains("HATA|HTTP", na=False)
                    count = int(mask.sum())
                    st.session_state.data = st.session_state.data[~mask].reset_index(drop=True)
                    st.success(f"🗑️ {count} hatalı kanal silindi.")
                    st.rerun()
                else:
                    st.info("Önce sağlık kontrolü yapın.")

            if st.button("🔤 Grup adlarını BÜYÜK HARF yap", use_container_width=True):
                push_undo()
                st.session_state.data["Grup"] = st.session_state.data["Grup"].astype(str).str.upper()
                st.success("Güncellendi.")
                st.rerun()

            if st.button("🔤 Grup adlarını Başlık Formatı yap", use_container_width=True):
                push_undo()
                st.session_state.data["Grup"] = st.session_state.data["Grup"].astype(str).str.title()
                st.success("Güncellendi.")
                st.rerun()

            if st.button("✨ Kanal adlarındaki fazla boşlukları temizle", use_container_width=True):
                push_undo()
                st.session_state.data["Kanal Adı"] = (
                    st.session_state.data["Kanal Adı"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
                )
                st.success("Temizlendi.")
                st.rerun()
        else:
            st.info("Önce bir playlist yükleyin.")


# =====================================================================
# FOOTER
# =====================================================================
st.markdown("---")

stats = st.session_state.visitor_counter.get_stats()

try:
    first_visit_str = datetime.fromisoformat(stats["first_visit"]).strftime("%d.%m.%Y")
except Exception:
    first_visit_str = "N/A"

try:
    last_visit_str = datetime.fromisoformat(stats["last_visit"]).strftime("%d.%m.%Y %H:%M")
except Exception:
    last_visit_str = "N/A"

st.markdown(
    f"<div style='text-align:center;padding:30px 20px;background:rgba(0,0,0,0.15);border-radius:12px;margin-top:40px;'>"
    f"<div style='margin-bottom:20px;'>"
    f"<h3 style='margin:0 0 15px 0;color:#aaa;font-size:1.1rem;'>📊 Ziyaretçi İstatistikleri</h3>"
    f"<div style='display:flex;justify-content:center;gap:40px;flex-wrap:wrap;'>"
    f"<div style='text-align:center;'><div style='font-size:0.75rem;color:#888;'>🌟 Benzersiz</div>"
    f"<div style='font-size:1.8rem;font-weight:bold;color:#FF4B4B;'>{stats['unique_visitors']}</div></div>"
    f"<div style='text-align:center;'><div style='font-size:0.75rem;color:#888;'>📊 Toplam</div>"
    f"<div style='font-size:1.8rem;font-weight:bold;color:#FF4B4B;'>{stats['total_visits']}</div></div>"
    f"<div style='text-align:center;'><div style='font-size:0.75rem;color:#888;'>📅 İlk</div>"
    f"<div style='font-size:1rem;font-weight:bold;color:#FF4B4B;'>{first_visit_str}</div></div>"
    f"<div style='text-align:center;'><div style='font-size:0.75rem;color:#888;'>🕒 Son</div>"
    f"<div style='font-size:1rem;font-weight:bold;color:#FF4B4B;'>{last_visit_str}</div></div>"
    f"</div></div>"
    f"<div style='border-top:1px solid rgba(255,255,255,0.1);padding-top:20px;margin-top:20px;'>"
    f"<p style='margin:0;font-size:0.85rem;color:#666;'>"
    f"© 2025 M3U Editör Pro v2.0 | "
    f"<a href='https://github.com/yourusername/m3uedit' target='_blank' style='color:#FF4B4B;text-decoration:none;'>GitHub</a> | "
    f"<a href='LICENSE' target='_blank' style='color:#FF4B4B;text-decoration:none;'>MIT Lisans</a></p>"
    f"<p style='margin:8px 0 0 0;font-size:0.7rem;color:#555;'>"
    f"Streamlit {st.__version__} | Python {sys.version.split()[0]}</p>"
    f"</div></div>",
    unsafe_allow_html=True,
)
