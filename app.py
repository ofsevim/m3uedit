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
from datetime import datetime

# --- MODÜL YOLLARI ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# --- YAPILANDIRMA ---
try:
    from utils.config import (
        PAGE_TITLE, PAGE_ICON, REQUEST_TIMEOUT, USER_AGENT, 
        DEFAULT_TR_FILTER, TABLE_HEIGHT, DISABLE_SSL_VERIFY,
        APP_VERSION
    )
except ImportError:
    PAGE_TITLE = "M3U Editör Pro"
    PAGE_ICON = "📺"
    REQUEST_TIMEOUT = 30
    USER_AGENT = "Mozilla/5.0"
    DEFAULT_TR_FILTER = True
    TABLE_HEIGHT = 600
    DISABLE_SSL_VERIFY = True
    APP_VERSION = "2.0.0"

# --- LOG ---
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", force=True)
logger = logging.getLogger(__name__)

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title=PAGE_TITLE,
    layout="wide",
    page_icon=PAGE_ICON,
    initial_sidebar_state="expanded",
)

# --- YARDIMCI MODÜLLER ---
from utils.parser import parse_m3u_lines, filter_channels, convert_df_to_m3u
from utils.visitor_counter import VisitorCounter

# --- CSS ---
def _load_css():
    css_path = os.path.join(current_dir, "static", "styles.css")
    try:
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except OSError:
        pass

_load_css()

# --- SSL CONTEXT ---
def _create_ssl_context():
    ctx = ssl.create_default_context()
    if DISABLE_SSL_VERIFY:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx

# --- SİSTEMLER ---
vc = VisitorCounter()

# =====================================================================
# YARDIMCI FONKSİYONLAR
# =====================================================================

def _safe_contains(series: pd.Series, term: str) -> pd.Series:
    return series.astype(str).str.contains(term, case=False, na=False)

def create_m3u_link(m3u_content: str) -> str:
    """Filtrelenmiş M3U içeriğini paste servisine yükleyip raw link döndürür."""
    # 1) paste.rs
    try:
        req = urllib.request.Request(
            "https://paste.rs/",
            data=m3u_content.encode("utf-8"),
            headers={"User-Agent": USER_AGENT, "Content-Type": "text/plain"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            paste_url = resp.read().decode("utf-8").strip()
            if paste_url.startswith("http"):
                return paste_url
    except Exception as e:
        logger.warning(f"paste.rs hatası: {e}")

    # 2) dpaste.com
    try:
        data = urllib.parse.urlencode({
            "content": m3u_content,
            "syntax": "text",
            "expiry_days": 365,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://dpaste.com/api/v2/",
            data=data,
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            paste_url = resp.read().decode("utf-8").strip().strip('"')
            if not paste_url.endswith(".txt"):
                paste_url = paste_url.rstrip("/") + ".txt"
            return paste_url
    except Exception as e:
        logger.error(f"M3U link oluşturma hatası: {e}", exc_info=True)
        return ""

def render_live_player(stream_url: str, height: int = 420) -> str:
    url = (stream_url or "").replace("'", "\\'").replace('"', '\\"')
    h = str(height)
    return f"""
    <div id='player_wrap' style='width:100%;height:{h}px;background:#000;border-radius:12px;overflow:hidden;position:relative;'>
        <video id='m3u_player' controls autoplay playsinline
               style='width:100%;height:100%;object-fit:contain;'></video>
        <div id='status_msg' style='display:none;color:#fff;padding:20px;text-align:center;
             position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:85%;'>
        </div>
        <div id='loading_indicator' style='position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
             color:#fff;font-size:1.3rem;'>⏳ Yükleniyor...</div>
    </div>
    <script src='https://cdn.jsdelivr.net/npm/hls.js@latest'></script>
    <script src='https://cdn.jsdelivr.net/npm/mpegts.js@latest/dist/mpegts.js'></script>
    <script>
    (function(){{
        var video = document.getElementById('m3u_player');
        var statusDiv = document.getElementById('status_msg');
        var loadDiv = document.getElementById('loading_indicator');
        var origUrl = '{url}';
        var proxyPrefixes = [
            '',
            'https://corsproxy.io/?',
            'https://api.allorigins.win/raw?url='
        ];
        var attempt = 0;
        var succeeded = false;

        function showFail(){{
            statusDiv.innerHTML =
                "<p style='font-size:1.1rem;margin:0 0 8px 0;'>⚠️ Tarayıcıda oynatılamıyor</p>"
                + "<p style='font-size:0.82rem;color:#94a3b8;margin:0 0 14px 0;'>CORS kısıtlaması — harici oynatıcı kullanın:</p>"
                + "<a href='vlc://{url}' style='display:inline-block;padding:8px 20px;background:#FF4B4B;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;font-size:0.85rem;margin:3px;'>▶ VLC</a>"
                + "<a href='potplayer://{url}' style='display:inline-block;padding:8px 20px;background:#334155;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;font-size:0.85rem;margin:3px;'>▶ PotPlayer</a>"
                + "<p style='margin:10px 0 0 0;'><button onclick=\\"navigator.clipboard.writeText('{url}');this.textContent='✅ Kopyalandı!'\\" "
                + "style='padding:7px 18px;background:#1e293b;color:#e2e8f0;border:1px solid rgba(255,255,255,0.15);border-radius:8px;cursor:pointer;font-size:0.82rem;'>📋 URL Kopyala</button></p>";
            statusDiv.style.display = 'block';
            video.style.display = 'none';
            loadDiv.style.display = 'none';
        }}

        function hideLoading(){{ loadDiv.style.display = 'none'; }}

        function showRetry(){{
            loadDiv.textContent = '🔄 CORS proxy deneniyor...';
        }}

        function tryPlay(streamUrl){{
            var isTS = streamUrl.toLowerCase().indexOf('.ts') !== -1 || origUrl.toLowerCase().indexOf('.ts') !== -1;
            var isHLS = streamUrl.toLowerCase().indexOf('.m3u8') !== -1 || origUrl.toLowerCase().indexOf('.m3u8') !== -1
                        || origUrl.toLowerCase().indexOf('/live/') !== -1;

            if (isTS && typeof mpegts !== 'undefined' && mpegts.isSupported()) {{
                var p = mpegts.createPlayer({{type:'mpegts',url:streamUrl,isLive:true}},
                    {{enableWorker:true,liveBufferLatencyChasing:true,liveSync:true}});
                p.attachMediaElement(video);
                p.load();
                p.play().catch(function(){{}});
                p.on(mpegts.Events.ERROR, function(){{ nextAttempt(); }});
                video.addEventListener('canplay', function(){{ succeeded=true; hideLoading(); }});
            }} else if ((isHLS || !isTS) && typeof Hls !== 'undefined' && Hls.isSupported()) {{
                var hls = new Hls({{enableWorker:true,lowLatencyMode:true,backBufferLength:90}});
                hls.loadSource(streamUrl);
                hls.attachMedia(video);
                hls.on(Hls.Events.MANIFEST_PARSED, function(){{ succeeded=true; hideLoading(); video.play().catch(function(){{}}); }});
                hls.on(Hls.Events.ERROR, function(ev,data){{
                    if(data.fatal) nextAttempt();
                }});
            }} else if (video.canPlayType('application/vnd.apple.mpegurl') || video.canPlayType('video/mp2t')) {{
                video.src = streamUrl;
                video.addEventListener('loadedmetadata', function(){{ succeeded=true; hideLoading(); video.play().catch(function(){{}}); }});
                video.addEventListener('error', function(){{ nextAttempt(); }});
            }} else {{
                nextAttempt();
            }}
        }}

        function nextAttempt(){{
            if (succeeded) return;
            attempt++;
            if (attempt < proxyPrefixes.length) {{
                showRetry();
                video.src = '';
                var proxyUrl = proxyPrefixes[attempt] + encodeURIComponent(origUrl);
                setTimeout(function(){{ tryPlay(proxyUrl); }}, 300);
            }} else {{
                showFail();
            }}
        }}

        if (!origUrl) {{ showFail(); return; }}
        tryPlay(origUrl);
        setTimeout(function(){{ if(!succeeded && attempt===0) nextAttempt(); }}, 6000);
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

# Ziyaretçi takibi
if "visited" not in st.session_state:
    vc.increment_visit(st.runtime.scriptrunner.add_script_run_ctx().id if hasattr(st.runtime.scriptrunner, "add_script_run_ctx") else None)
    st.session_state.visited = True

# =====================================================================
# SIDEBAR
# =====================================================================

with st.sidebar:
    st.markdown(
        f"<div style='text-align:center;padding:0.3rem 0;'>"
        f"<span style='font-size:1.2rem;'>{PAGE_ICON}</span> "
        f"<span style='font-size:0.95rem;font-weight:600;color:#f1f5f9;'>{PAGE_TITLE}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    url = st.text_input("🌐 M3U Linki Yapıştır:")
    uploaded_file = st.file_uploader("📂 veya M3U Dosyası Yükle", type=["m3u", "m3u8"])
    only_tr = st.checkbox("🇹🇷 Sadece TR Kanalları", value=DEFAULT_TR_FILTER)

    if st.button("🚀 Listeyi Çek ve Tara", use_container_width=True, type="primary"):
        source_lines = None
        start = time.time()
        if url:
            try:
                with st.spinner("Link indiriliyor..."):
                    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                    ctx = _create_ssl_context()
                    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx) as resp:
                        source_lines = resp.readlines()
            except urllib.error.HTTPError as e:
                st.error(f"🚫 HTTP Hatası: {e.code}")
            except urllib.error.URLError as e:
                st.error(f"🔌 Bağlantı Hatası: {e.reason}")
            except Exception as e:
                logger.error("Yükleme hatası", exc_info=True)
                st.error(f"❌ Hata: {e}")
        elif uploaded_file:
            source_lines = io.StringIO(uploaded_file.getvalue().decode("utf-8", errors="ignore")).readlines()
        else:
            st.warning("Lütfen bir link girin veya dosya yükleyin.")

        if source_lines:
            raw = parse_m3u_lines(source_lines)
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
            selected_groups = st.multiselect("Grupları filtrele", group_options, default=None, key="group_filter")

    # İstatistikler
    st.markdown("---")
    stats = vc.get_stats()
    st.markdown(f"**👥 Toplam Ziyaret:** {stats['total_visits']}")
    st.markdown(f"**👤 Tekil Ziyaretçi:** {stats['unique_visitors']}")
    
    last_visit = datetime.fromisoformat(stats['last_visit']).strftime("%d.%m.%Y %H:%M")
    st.caption(f"Son Ziyaret: {last_visit}")

# =====================================================================
# ANA EKRAN
# =====================================================================

if not st.session_state.data.empty:
    # Filtreleme
    df_display = st.session_state.data.copy()
    if selected_groups:
        df_display = df_display[df_display["Grup"].isin(selected_groups)]

    # Arama
    search_term = st.text_input("🔍 Kanal Ara:", "", placeholder="Kanal adı veya grup yazın...")
    if search_term:
        df_display = df_display[
            _safe_contains(df_display["Kanal Adı"], search_term)
            | _safe_contains(df_display["Grup"], search_term)
        ]

    # Metrikler
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("📺 Kanal", len(df_display))
    mc2.metric("📁 Grup", df_display["Grup"].nunique())
    hls_count = int((df_display["Tür"] == "HLS").sum()) if "Tür" in df_display.columns else 0
    mc3.metric("📡 HLS", hls_count)

    st.caption(f"Gösterilen: {len(df_display)} / {len(st.session_state.data)} kanal")

    # --- Dışa Aktar & Link ---
    m3u_out = convert_df_to_m3u(df_display)
    exp1, exp2 = st.columns(2)
    with exp1:
        st.download_button(
            label=f"📥 M3U İndir ({len(df_display)} kanal)",
            data=m3u_out,
            file_name="iptv_listesi.m3u",
            mime="text/plain",
            type="primary",
            use_container_width=True,
        )
    with exp2:
        if st.button("🔗 M3U Link Oluştur", use_container_width=True):
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
            "URL": st.column_config.TextColumn("URL", width="large"),
            "Tür": st.column_config.TextColumn("Tür", width="small"),
        },
    )

else:
    st.markdown(
        f"<div style='text-align:center;padding:80px 20px;'>"
        f"<div style='font-size:4rem;margin-bottom:1rem;'>{PAGE_ICON}</div>"
        f"<h2 style='color:#f1f5f9;'>{PAGE_TITLE}</h2>"
        f"<p style='color:#94a3b8;font-size:1.1rem;max-width:500px;margin:1rem auto;'>"
        f"Sol menüden bir M3U linki yapıştırın ve TR kanallarını kolayca filtreleyin.</p>"
        f"</div>",
        unsafe_allow_html=True,
    )

# --- Footer ---
st.markdown("---")
st.markdown(
    "<div style='text-align:center;padding:15px;'>"
    "<p style='margin:0;font-size:0.8rem;color:#64748b;'>"
    f"{PAGE_TITLE} v{APP_VERSION} | Streamlit {st.__version__} | Python {sys.version.split()[0]}</p>"
    "</div>",
    unsafe_allow_html=True,
)
