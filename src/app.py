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
import logging
from typing import Iterable, List, Dict

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
        "About": "# M3U Editör Pro\nIPTV playlist yönetim aracı",
    },
)

# --- MODÜL YOLLARI ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

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


# --- GEÇMİŞ (HISTORY) ---
HISTORY_FILE = os.path.join(parent_dir, "history.json")


def _load_history() -> list:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Geçmiş yüklenemedi: {e}")
        return []


def _save_history(hist: list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(f"Geçmiş kaydedilemedi: {e}")


def add_history(entry: dict):
    hist = _load_history()
    hist.append(entry)
    _save_history(hist)


# --- CSS ---
css_path = os.path.join(parent_dir, "static", "styles.css")
try:
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except OSError as e:
    logger.warning(f"CSS yüklenemedi: {e}")


# --- GLOBAL TANIMLAMALAR ---
TR_PATTERN = re.compile(
    r"(\b|_|\[|\(|\|)(TR|TURK|TÜRK|TURKIYE|TÜRKİYE|YERLI|ULUSAL|ISTANBUL)(\b|_|\]|\)|\||:)",
    re.IGNORECASE,
)


# --- FONKSİYONLAR ---
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
                channels.append(current_info)
                current_info = None

    return channels


def filter_channels(channels: List[Dict], only_tr: bool = False) -> List[Dict]:
    """Kanal listesini TR filtresine göre filtreler."""
    if not only_tr:
        return channels
    return [ch for ch in channels if TR_PATTERN.search(ch.get("Grup", ""))]


def convert_df_to_m3u(df: pd.DataFrame) -> str:
    """DataFrame'i M3U formatına dönüştürür."""
    lines = ["#EXTM3U"]
    for _, row in df.iterrows():
        logo = row.get("LogoURL", "")
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        lines.append(f'#EXTINF:-1{logo_attr} group-title="{row["Grup"]}",{row["Kanal Adı"]}')
        lines.append(str(row["URL"]))
    return "\n".join(lines) + "\n"


def render_live_player(stream_url: str, height: int = 420) -> str:
    """HLS video oynatıcı HTML snippet'i döndürür."""
    url = (stream_url or "").replace("'", "\\'").replace('"', '\\"')
    h = str(height)

    return f"""
    <div style='width:100%;height:{h}px;background:#000;border-radius:8px;overflow:hidden;'>
        <video id='m3u_player' controls autoplay playsinline style='width:100%;height:100%;'></video>
        <div id='error_msg' style='display:none;color:#fff;padding:20px;text-align:center;'>
            <p>⚠️ Video yüklenemedi. URL geçerli olmayabilir veya CORS hatası olabilir.</p>
        </div>
    </div>
    <script src='https://cdn.jsdelivr.net/npm/hls.js@latest'></script>
    <script>
        var video = document.getElementById('m3u_player');
        var errorDiv = document.getElementById('error_msg');
        var url = '{url}';
        if (!url) {{
            errorDiv.style.display = 'block'; video.style.display = 'none';
        }} else if (Hls.isSupported()) {{
            var hls = new Hls({{enableWorker:true,lowLatencyMode:true,backBufferLength:90}});
            hls.loadSource(url); hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, function(){{ video.play().catch(function(){{}}); }});
            hls.on(Hls.Events.ERROR, function(event,data){{
                if(data.fatal){{ errorDiv.style.display='block'; video.style.display='none'; }}
            }});
        }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
            video.src = url;
            video.addEventListener('loadedmetadata', function(){{ video.play().catch(function(){{}}); }});
            video.addEventListener('error', function(){{ errorDiv.style.display='block'; video.style.display='none'; }});
        }} else {{
            errorDiv.innerHTML = '<p>⚠️ Tarayıcınız HLS formatını desteklemiyor.</p>';
            errorDiv.style.display = 'block'; video.style.display = 'none';
        }}
    </script>
    """


def _create_ssl_context():
    """SSL context oluşturur (sertifika doğrulaması devre dışı)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _safe_contains(series: pd.Series, term: str) -> pd.Series:
    """NaN-güvenli string arama."""
    return series.astype(str).str.contains(term, case=False, na=False)


# =====================================================================
# ARAYÜZ (UI)
# =====================================================================

# Ziyaretçi sayacı
if "visitor_counter" not in st.session_state:
    st.session_state.visitor_counter = VisitorCounter()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.visitor_counter.increment_visit(st.session_state.session_id)

if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Seç", "Grup", "Kanal Adı", "URL"])

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(
        """
        <div style='text-align:center;padding:1rem 0;'>
            <h1 style='margin:0;font-size:2rem;'>📺</h1>
            <h2 style='margin:0.5rem 0 0 0;font-size:1.5rem;'>M3U Editör Pro</h2>
            <p style='margin:0.25rem 0 0 0;color:#888;font-size:0.9rem;'>IPTV Yönetim Aracı</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

    mode = st.radio("Yükleme Yöntemi", ["🌐 Linkten Yükle", "📂 Dosya Yükle"])

    # Grup filtreleme (veri varsa)
    selected_groups = []
    if not st.session_state.data.empty:
        sort_by = st.selectbox("Sırala", ["Grup", "Kanal Adı", "URL"], index=0)
        sort_dir = st.radio("Yön", ["A → Z", "Z → A"], index=0)

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
        url = st.text_input("M3U Linki Yapıştır:")
        only_tr = st.checkbox("🇹🇷 SADECE GRUPTA ARA (TR Filtresi)", value=DEFAULT_TR_FILTER)

        if st.button("Listeyi Çek ve Tara", use_container_width=True):
            if url:
                try:
                    with st.spinner("Link indiriliyor ve taranıyor..."):
                        headers = {"User-Agent": USER_AGENT}
                        req = urllib.request.Request(url, headers=headers)
                        ctx = _create_ssl_context()

                        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx) as response:
                            raw_channels = parse_m3u_lines(response)
                            final_channels = filter_channels(raw_channels, only_tr)
                            new_data = pd.DataFrame(final_channels)
                            duplicates = (
                                new_data.duplicated(subset=["Grup", "Kanal Adı", "URL"]).sum()
                                if not new_data.empty
                                else 0
                            )

                            if not final_channels:
                                st.warning("⚠️ Linkten veri çekildi ama kanal bulunamadı veya format hatalı.")
                            else:
                                st.success(f"✅ Toplam {len(final_channels)} kanal bulundu.")
                                add_history({"type": "load", "count": len(final_channels), "url": url, "time": time.time()})
                            if duplicates:
                                st.info(f"⚠️ {int(duplicates)} tekrarlı kanal tespit edildi.")

                except urllib.error.HTTPError as e:
                    st.error(f"🚫 HTTP Hatası: {e.code} - {e.reason}")
                except urllib.error.URLError as e:
                    st.error(f"🔌 Bağlantı Hatası: {e.reason}")
                except TimeoutError:
                    st.error(f"⏱️ Zaman Aşımı: Sunucu {REQUEST_TIMEOUT} saniye içinde yanıt vermedi.")
                except Exception as e:
                    logger.error("Kanal yükleme hatası", exc_info=True)
                    st.error(f"❌ Beklenmeyen Hata: {e}")
            else:
                st.warning("Lütfen bir link girin.")

    elif mode == "📂 Dosya Yükle":
        uploaded_file = st.file_uploader("M3U Dosyası Seç", type=["m3u", "m3u8"])
        if uploaded_file is not None:
            stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8", errors="ignore"))
            raw_channels = parse_m3u_lines(stringio)
            new_data = pd.DataFrame(raw_channels)
            st.success(f"Dosya yüklendi. {len(raw_channels)} kanal.")

    if new_data is not None:
        for col, default in [("Seç", False), ("Favori", False), ("LogoURL", ""), ("Durum", "")]:
            if col not in new_data.columns:
                new_data.insert(0 if col == "Seç" else len(new_data.columns), col, default)
        st.session_state.data = new_data

    st.markdown("---")

    if not st.session_state.data.empty:
        selected_rows = st.session_state.data[st.session_state.data["Seç"] == True]
        count_selected = len(selected_rows)

        if count_selected > 0:
            st.success(f"✅ {count_selected} kanal seçildi.")
            download_df = selected_rows
            btn_label = f"💾 SEÇİLENLERİ İNDİR ({count_selected})"
            file_name_suffix = "_secilenler"
        else:
            st.info("ℹ️ Seçim yok, tüm liste indirilecek.")
            download_df = st.session_state.data
            btn_label = "💾 TÜM LİSTEYİ İNDİR"
            file_name_suffix = "_tum_liste"

        m3u_output = convert_df_to_m3u(download_df)
        st.download_button(
            label=btn_label,
            data=m3u_output,
            file_name=f"{DEFAULT_EXPORT_FILENAME}{file_name_suffix}{EXPORT_FILE_EXTENSION}",
            mime="text/plain",
            type="primary",
            use_container_width=True,
        )

        # URL sağlık kontrolü
        if st.button("🔍 URL Sağlık Kontrolü"):
            with st.spinner("Sağlık kontrolü çalışıyor..."):
                df = st.session_state.data.copy()
                statuses = []
                for u in df["URL"].astype(str):
                    if not u or u.strip() == "":
                        statuses.append("Boş URL")
                        continue
                    try:
                        with urllib.request.urlopen(u, timeout=5) as resp:
                            code = getattr(resp, "status", 200)
                            statuses.append("OK" if int(code) < 400 else str(code))
                    except Exception:
                        statuses.append("HATA")
                df["Durum"] = statuses
                st.session_state.data = df
                st.success("Durumlar güncellendi.")


# --- ANA EKRAN ---
st.subheader("Kanal Listesi Düzenleyici")

if not st.session_state.data.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Toplam Kanal", len(st.session_state.data))
    selected_count = len(st.session_state.data[st.session_state.data["Seç"] == True])
    col2.metric("Seçilen Kanal", selected_count)
    col3.metric("Grup Sayısı", st.session_state.data["Grup"].nunique())

    search_term = st.text_input("🔍 Tablo içinde ara (Grup veya Kanal Adı):", "")

    df_display = st.session_state.data
    if selected_groups:
        df_display = df_display[df_display["Grup"].isin(selected_groups)]
    if search_term:
        df_display = df_display[
            _safe_contains(df_display["Grup"], search_term)
            | _safe_contains(df_display["Kanal Adı"], search_term)
        ]

    # Oynatıcı
    if "play_channel" not in st.session_state:
        st.session_state.play_channel = None

    st.markdown("### 🎬 Canlı Oynatıcı")
    col_play1, col_play2 = st.columns([3, 1])
    with col_play1:
        play_channel_name = st.selectbox(
            "Oynatılacak Kanal",
            options=df_display["Kanal Adı"].tolist() if not df_display.empty else [],
            index=None,
            placeholder="Kanal seçin...",
            key="play_select",
        )
    with col_play2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("▶ OYNAT", use_container_width=True, key="play_btn"):
            if play_channel_name:
                selected_row = df_display[df_display["Kanal Adı"] == play_channel_name]
                if not selected_row.empty:
                    st.session_state.play_channel = {
                        "name": play_channel_name,
                        "url": selected_row.iloc[0]["URL"],
                        "logo": selected_row.iloc[0].get("LogoURL", ""),
                    }
                    st.rerun()

    if st.session_state.play_channel:
        pc = st.session_state.play_channel
        st.markdown(f"**▶ Oynatılıyor:** {pc['name']}")

        if pc.get("logo"):
            try:
                st.image(pc["logo"], width=100)
            except Exception:
                pass

        components.html(render_live_player(pc["url"], height=400), height=500)

        if st.button("⏹ Oynatmayı Durdur", use_container_width=True):
            st.session_state.play_channel = None
            st.rerun()

        st.markdown("---")

    st.caption("İstediğiniz kanalların başındaki kutucuğu işaretleyin.")

    edited_df = st.data_editor(
        df_display,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        height=TABLE_HEIGHT,
        key="editor",
    )

    if edited_df is not None and not edited_df.equals(df_display):
        st.session_state.data.update(edited_df)

else:
    st.info("👈 Başlamak için sol menüden bir link yapıştırın veya dosya yükleyin.")

# --- FOOTER ---
st.markdown("---")

stats = st.session_state.visitor_counter.get_stats()

try:
    from datetime import datetime as _dt

    first_visit_str = _dt.fromisoformat(stats["first_visit"]).strftime("%d.%m.%Y")
except Exception:
    first_visit_str = "N/A"

try:
    from datetime import datetime as _dt

    last_visit_str = _dt.fromisoformat(stats["last_visit"]).strftime("%d.%m.%Y")
except Exception:
    last_visit_str = "N/A"

st.markdown(
    f"""
    <div style='text-align:center;padding:30px 20px;background:rgba(0,0,0,0.02);border-radius:10px;margin-top:40px;'>
        <div style='margin-bottom:20px;'>
            <h3 style='margin:0 0 15px 0;color:#555;font-size:1.2rem;'>📊 Ziyaretçi İstatistikleri</h3>
            <div style='display:flex;justify-content:center;gap:30px;flex-wrap:wrap;'>
                <div style='text-align:center;'>
                    <div style='font-size:0.8rem;color:#888;'>🌟 Benzersiz Ziyaretçi</div>
                    <div style='font-size:1.5rem;font-weight:bold;color:#FF4B4B;'>{stats['unique_visitors']}</div>
                </div>
                <div style='text-align:center;'>
                    <div style='font-size:0.8rem;color:#888;'>📊 Toplam Kayıt</div>
                    <div style='font-size:1.5rem;font-weight:bold;color:#FF4B4B;'>{stats['total_visits']}</div>
                </div>
                <div style='text-align:center;'>
                    <div style='font-size:0.8rem;color:#888;'>📅 İlk Ziyaret</div>
                    <div style='font-size:1.5rem;font-weight:bold;color:#FF4B4B;'>{first_visit_str}</div>
                </div>
                <div style='text-align:center;'>
                    <div style='font-size:0.8rem;color:#888;'>🕒 Son Ziyaret</div>
                    <div style='font-size:1.5rem;font-weight:bold;color:#FF4B4B;'>{last_visit_str}</div>
                </div>
            </div>
        </div>
        <div style='border-top:1px solid #ddd;padding-top:20px;margin-top:20px;'>
            <p style='margin:0;font-size:0.9rem;color:#666;'>
                © 2025 M3U Editör Pro |
                <a href='https://github.com/yourusername/m3uedit' target='_blank' style='color:#FF4B4B;text-decoration:none;'>GitHub</a> |
                <a href='docs/KULLANIM_KILAVUZU.md' target='_blank' style='color:#FF4B4B;text-decoration:none;'>Dokümantasyon</a> |
                <a href='LICENSE' target='_blank' style='color:#FF4B4B;text-decoration:none;'>MIT Lisans</a>
            </p>
            <p style='margin:10px 0 0 0;font-size:0.75rem;color:#999;'>
                Streamlit {st.__version__} ile geliştirildi
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
