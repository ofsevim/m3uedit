import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import urllib.request
import urllib.error
import ssl
import re
import io
import os
import sys
import time
import logging
import urllib.parse
from typing import Iterable, List, Dict

# --- LOG ---
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", force=True)
logger = logging.getLogger(__name__)

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="M3U Editör Pro",
    layout="wide",
    page_icon="📺",
    initial_sidebar_state="expanded",
)

# --- MODÜL YOLLARI ---
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from utils.config import REQUEST_TIMEOUT, USER_AGENT, DEFAULT_TR_FILTER, TABLE_HEIGHT
except ImportError:
    REQUEST_TIMEOUT = 30
    USER_AGENT = "Mozilla/5.0"
    DEFAULT_TR_FILTER = True
    TABLE_HEIGHT = 600

# --- CSS ---
def _load_css():
    for path in [os.path.join(current_dir, "static", "styles.css"),
                 os.path.join(os.getcwd(), "static", "styles.css")]:
        try:
            with open(path, encoding="utf-8") as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
                return
        except OSError:
            continue

_load_css()


# =====================================================================
# YARDIMCI FONKSİYONLAR
# =====================================================================

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


def parse_m3u_lines(iterator: Iterable) -> List[Dict]:
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
            logo = re.search(r'tvg-logo="([^"]*)"', line)
            if logo:
                info["LogoURL"] = logo.group(1)
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
                lower = line.lower()
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
    result = channels
    if only_tr:
        result = [ch for ch in result if TR_PATTERN.search(ch.get("Grup", "") + " " + ch.get("Kanal Adı", ""))]
    if keyword:
        kw = keyword.lower()
        result = [ch for ch in result if kw in ch.get("Kanal Adı", "").lower() or kw in ch.get("Grup", "").lower()]
    if group_filter:
        result = [ch for ch in result if ch.get("Grup", "") == group_filter]
    return result


def convert_df_to_m3u(df: pd.DataFrame) -> str:
    lines = ["#EXTM3U"]
    for _, row in df.iterrows():
        logo = row.get("LogoURL", "")
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        lines.append(f'#EXTINF:-1{logo_attr} group-title="{row["Grup"]}",{row["Kanal Adı"]}')
        lines.append(str(row["URL"]))
    return "\n".join(lines) + "\n"


def create_m3u_link(m3u_content: str) -> str:
    """Filtrelenmiş M3U içeriğini dpaste.org'a yükleyip raw link döndürür."""
    try:
        data = urllib.parse.urlencode({
            "content": m3u_content,
            "syntax": "text",
            "expiry_days": 7,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://dpaste.org/api/",
            data=data,
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            paste_url = resp.read().decode("utf-8").strip().strip('"')
            # dpaste raw formatı: URL sonuna /raw ekle
            if not paste_url.endswith("/raw"):
                paste_url = paste_url.rstrip("/") + "/raw"
            return paste_url
    except Exception as e:
        logger.error(f"M3U link oluşturma hatası: {e}", exc_info=True)
        return ""


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

if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame()
if "play_channel" not in st.session_state:
    st.session_state.play_channel = None


# =====================================================================
# SIDEBAR
# =====================================================================

with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:1rem 0;'>"
        "<h1 style='margin:0;font-size:2.5rem;'>📺</h1>"
        "<h2 style='margin:0.5rem 0 0 0;font-size:1.4rem;color:#f1f5f9;'>M3U Editör Pro</h2>"
        "<p style='margin:0.25rem 0 0 0;color:#94a3b8;font-size:0.85rem;'>IPTV Kanal Filtresi & Oynatıcı</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    url = st.text_input("🌐 M3U Linki Yapıştır:")
    only_tr = st.checkbox("🇹🇷 Sadece TR Kanalları", value=DEFAULT_TR_FILTER)

    if st.button("🚀 Listeyi Çek ve Tara", use_container_width=True, type="primary"):
        if url:
            try:
                with st.spinner("Link indiriliyor ve taranıyor..."):
                    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                    ctx = _create_ssl_context()
                    start = time.time()
                    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx) as resp:
                        raw = parse_m3u_lines(resp)
                        filtered = filter_channels(raw, only_tr)
                        elapsed = round(time.time() - start, 2)
                        if filtered:
                            df = pd.DataFrame(filtered)
                            for col, default in [("LogoURL", ""), ("Tür", "")]:
                                if col not in df.columns:
                                    df[col] = default
                            st.session_state.data = df
                            st.success(f"✅ {len(filtered)} kanal bulundu ({elapsed}s)")
                        else:
                            st.warning("⚠️ Kanal bulunamadı.")
            except urllib.error.HTTPError as e:
                st.error(f"🚫 HTTP Hatası: {e.code}")
            except urllib.error.URLError as e:
                st.error(f"🔌 Bağlantı Hatası: {e.reason}")
            except TimeoutError:
                st.error(f"⏱️ Zaman Aşımı ({REQUEST_TIMEOUT}s)")
            except Exception as e:
                logger.error("Yükleme hatası", exc_info=True)
                st.error(f"❌ Hata: {e}")
        else:
            st.warning("Lütfen bir link girin.")

    st.markdown("---")

    # Filtreler (veri yüklendiyse)
    selected_groups = []
    if not st.session_state.data.empty:
        st.markdown("#### ⚙️ Filtre")
        try:
            group_options = sorted(st.session_state.data["Grup"].astype(str).dropna().unique())
        except Exception:
            group_options = []
        if group_options:
            selected_groups = st.multiselect("Grupları filtrele", group_options, default=group_options)

        st.markdown("---")
        st.markdown("#### 💾 Dışa Aktar")
        m3u_out = convert_df_to_m3u(st.session_state.data)
        st.download_button(
            label=f"📥 M3U İndir ({len(st.session_state.data)} kanal)",
            data=m3u_out,
            file_name="iptv_listesi.m3u",
            mime="text/plain",
            type="primary",
            use_container_width=True,
        )

        st.markdown("---")
        st.markdown("#### 🔗 M3U Link Oluştur")
        st.caption("Filtrelenmiş listeyi online M3U linki olarak paylaş (7 gün geçerli)")
        if st.button("🔗 Link Oluştur", use_container_width=True):
            with st.spinner("Link oluşturuluyor..."):
                link = create_m3u_link(m3u_out)
            if link:
                st.session_state.m3u_link = link
                st.success("Link hazır!")
            else:
                st.error("Link oluşturulamadı.")

        if st.session_state.get("m3u_link"):
            st.code(st.session_state.m3u_link, language=None)
            st.caption("☝️ Bu linki IPTV oynatıcına yapıştırabilirsin.")


# =====================================================================
# ANA EKRAN
# =====================================================================

if not st.session_state.data.empty:
    # Metrikler
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("📺 Toplam Kanal", len(st.session_state.data))
    mc2.metric("📁 Grup", st.session_state.data["Grup"].nunique())
    hls_count = int((st.session_state.data.get("Tür", pd.Series()) == "HLS").sum()) if "Tür" in st.session_state.data.columns else 0
    mc3.metric("📡 HLS", hls_count)

    # Arama
    search_term = st.text_input("🔍 Kanal Ara:", "", placeholder="Kanal adı veya grup yazın...")

    # Filtreleme
    df_display = st.session_state.data.copy()
    if selected_groups:
        df_display = df_display[df_display["Grup"].isin(selected_groups)]
    if search_term:
        df_display = df_display[
            _safe_contains(df_display["Kanal Adı"], search_term)
            | _safe_contains(df_display["Grup"], search_term)
        ]

    st.caption(f"Gösterilen: {len(df_display)} / {len(st.session_state.data)} kanal")

    # --- Canlı Oynatıcı ---
    st.markdown("### 🎬 Canlı Oynatıcı")
    col1, col2 = st.columns([4, 1])
    with col1:
        play_options = df_display["Kanal Adı"].tolist() if not df_display.empty else []
        play_name = st.selectbox("Oynatılacak Kanal", options=play_options,
                                 index=None, placeholder="Kanal seçin...", key="play_select")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("▶ OYNAT", use_container_width=True, type="primary"):
            if play_name:
                row = df_display[df_display["Kanal Adı"] == play_name]
                if not row.empty:
                    st.session_state.play_channel = {
                        "name": play_name,
                        "url": row.iloc[0]["URL"],
                        "logo": row.iloc[0].get("LogoURL", ""),
                        "group": row.iloc[0].get("Grup", ""),
                    }
                    st.rerun()

    if st.session_state.play_channel:
        pc = st.session_state.play_channel
        pcol1, pcol2 = st.columns([1, 4])
        with pcol1:
            if pc.get("logo"):
                try:
                    st.image(pc["logo"], width=120)
                except Exception:
                    pass
            st.markdown(f"<span style='color:#94a3b8;'>Grup:</span> <span style='color:#f1f5f9;font-weight:600;'>{pc.get('group', '')}</span>", unsafe_allow_html=True)
        with pcol2:
            st.markdown(f"### ▶ {pc['name']}")
            components.html(render_live_player(pc["url"], height=380), height=420)

        if st.button("⏹ Durdur", use_container_width=True):
            st.session_state.play_channel = None
            st.rerun()
        st.markdown("---")

    # --- Kanal Tablosu ---
    display_cols = [c for c in ["Grup", "Kanal Adı", "URL", "Tür"] if c in df_display.columns]
    st.dataframe(
        df_display[display_cols] if display_cols else df_display,
        use_container_width=True, hide_index=True, height=TABLE_HEIGHT,
        column_config={
            "URL": st.column_config.LinkColumn("URL", width="large"),
            "Tür": st.column_config.TextColumn("Tür", width="small"),
        },
    )

else:
    st.markdown(
        "<div style='text-align:center;padding:80px 20px;'>"
        "<div style='font-size:4rem;margin-bottom:1rem;'>📺</div>"
        "<h2 style='color:#f1f5f9;'>M3U Editör Pro</h2>"
        "<p style='color:#94a3b8;font-size:1.1rem;max-width:500px;margin:1rem auto;'>"
        "Sol menüden bir M3U linki yapıştırın ve TR kanallarını kolayca filtreleyin.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

# --- Footer ---
st.markdown("---")
st.markdown(
    "<div style='text-align:center;padding:15px;'>"
    "<p style='margin:0;font-size:0.8rem;color:#64748b;'>"
    f"M3U Editör Pro | Streamlit {st.__version__} | Python {sys.version.split()[0]}</p>"
    "</div>",
    unsafe_allow_html=True,
)
