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
        APP_VERSION, HEALTH_CHECK_MAX_WORKERS, HEALTH_CHECK_TIMEOUT
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
    HEALTH_CHECK_MAX_WORKERS = 10
    HEALTH_CHECK_TIMEOUT = 5

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
from utils.parser import parse_m3u_lines, filter_channels, convert_df_to_m3u, batch_check_health
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

def render_live_player(stream_url: str, height: int = 420, cors_restricted: bool = False) -> str:
    url = (stream_url or "").replace("'", "\\'").replace('"', '\\"')
    h = str(height)
    start_proxy_idx = 1 if cors_restricted else 0
    return f"""
    <link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet" />
    <link href="https://unpkg.com/@videojs/themes@1.0.1/dist/city/index.css" rel="stylesheet">
    <style>
        .player-container {{ 
            position: relative; width: 100%; height: {h}px; background: #000; 
            border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); 
        }}
        .video-js {{ width: 100%; height: 100%; }}
        .vjs-city .vjs-big-play-button {{ 
            left: 50% !important; top: 50% !important; transform: translate(-50%, -50%) !important;
            margin: 0 !important; width: 2.5em !important; height: 2.5em !important; border-radius: 50% !important;
        }}
        #player-status {{ 
            position: absolute; top: 0; left: 0; right: 0; bottom: 0; 
            display: flex; align-items: center; justify-content: center; 
            z-index: 20; pointer-events: none; text-align: center; color: #fff;
        }}
        #player-status.active {{ background: rgba(0,0,0,0.6); pointer-events: auto; }}
        #player-status .msg-box {{ 
            background: rgba(15, 23, 42, 0.9); padding: 20px 30px; border-radius: 16px; 
            font-size: 0.95rem; border: 1px solid rgba(255,255,255,0.2); backdrop-filter: blur(8px);
        }}
        .retry-btn {{ 
            margin-top: 15px; padding: 10px 20px; background: #3b82f6; color: white; 
            border: none; border-radius: 8px; cursor: pointer; font-size: 0.85rem; font-weight: 600;
        }}
        .vlc-btn {{ 
            margin-top: 10px; padding: 10px 20px; background: #ef4444; color: white; 
            border: none; border-radius: 8px; cursor: pointer; font-size: 0.85rem; font-weight: 600; text-decoration: none; display: inline-block;
        }}
    </style>

    <div class="player-container">
        <video id="iptv-player" class="video-js vjs-theme-city vjs-big-play-centered">
        </video>
        <div id="player-status">
            <div class="msg-box" id="status-box">
                <div id="status-text">⏳ Başlatılıyor...</div>
            </div>
        </div>
    </div>

    <script src="https://vjs.zencdn.net/8.10.0/video.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <script src="https://cdn.jsdelivr.net/npm/mpegts.js@latest/dist/mpegts.js"></script>

    <script>
    (function(){{
        var player = videojs('iptv-player', {{
            autoplay: true,
            controls: true,
            responsive: true,
            fluid: false,
            liveui: true,
            preload: 'auto'
        }});

        var statusEl = document.getElementById('player-status');
        var statusBox = document.getElementById('status-box');
        var statusText = document.getElementById('status-text');
        var origUrl = '{url}';
        var proxies = [
            '', 
            'https://api.allorigins.win/raw?url=',
            'https://corsproxy.io/?'
        ];
        var currentIdx = {start_proxy_idx};
        var hasSucceeded = false;

        function showStatus(msg, isPersistent) {{
            statusText.innerHTML = msg;
            statusEl.style.display = 'flex';
            if (isPersistent) {{
                statusEl.classList.add('active');
            }} else {{
                statusEl.classList.remove('active');
            }}
        }}

        function hideStatus() {{
            statusEl.style.display = 'none';
        }}

        function startPlay(url) {{
            if (hasSucceeded) return;
            
            var lower = url.toLowerCase();
            var ctx = proxies[currentIdx] ? ' (CORS Proxy ' + currentIdx + ' aktif)' : '';
            showStatus('🔄 Kanal yükleniyor' + ctx + '...', false);

            if (lower.includes('.m3u8') || lower.includes('/live/')) {{
                if (Hls.isSupported()) {{
                    var hls = new Hls({{ enableWorker: true, lowLatencyMode: true }});
                    hls.loadSource(url);
                    hls.attachMedia(player.tech().el());
                    hls.on(Hls.Events.MANIFEST_PARSED, function() {{ 
                        hasSucceeded = true; hideStatus(); player.play().catch(e => {{}}); 
                    }});
                    hls.on(Hls.Events.ERROR, function(e, d) {{ if (d.fatal) tryNext(); }});
                }} else {{
                    player.src({{ src: url, type: 'application/x-mpegURL' }});
                }}
            }} else if (lower.includes('.ts')) {{
                if (mpegts.isSupported()) {{
                    var m = mpegts.createPlayer({{ type: 'mpegts', url: url, isLive: true }});
                    m.attachMediaElement(player.tech().el());
                    m.load();
                    m.play();
                    hasSucceeded = true; hideStatus();
                }}
            }} else {{
                player.src({{ src: url, type: 'video/mp4' }});
            }}
        }}

        function tryNext() {{
            if (hasSucceeded) return;
            currentIdx++;
            if (currentIdx < proxies.length) {{
                var nextUrl = proxies[currentIdx] + (proxies[currentIdx] ? encodeURIComponent(origUrl) : origUrl);
                startPlay(nextUrl);
            }} else {{
                var failHtml = '🚫 Oynatılamadı (CORS veya Link Hatası)<br>' +
                    '<p style="font-size:0.8rem;color:#94a3b8;margin:5px 0 10px 0;">Tarayıcı kısıtlaması nedeniyle açılamadı.</p>' +
                    '<button class="retry-btn" onclick="location.reload()" style="margin:5px;">🔄 Yeniden Dene</button>' +
                    '<button class="retry-btn" style="background:#10b981;margin:5px;" onclick="navigator.clipboard.writeText(\\''+origUrl+'\\');this.textContent=\\'✅ Kopyalandı!\\'">📋 URL Kopyala</button><br>' +
                    '<div style="margin-top:10px;border-top:1px solid rgba(255,255,255,0.1);padding-top:10px;">' +
                        '<a href="vlc://' + origUrl + '" class="vlc-btn" style="margin:3px;">▶ VLC</a>' +
                        '<a href="potplayer://' + origUrl + '" class="vlc-btn" style="background:#334155;margin:3px;">▶ PotPlayer</a>' +
                    '</div>' +
                    '<p style="font-size:0.75rem;color:#64748b;margin-top:8px;">*Protocol handler yüklü olmalıdır.</p>';
                showStatus(failHtml, true);
            }}
        }}

        player.on('playing', function() {{ hasSucceeded = true; hideStatus(); }});
        player.on('error', function() {{ tryNext(); }});

        if (!origUrl) {{ showStatus('⚠️ Geçersiz URL', true); }}
        else {{ 
            var initialUrl = proxies[currentIdx] + (proxies[currentIdx] ? encodeURIComponent(origUrl) : origUrl);
            startPlay(initialUrl); 
        }}

        setTimeout(function() {{ if (!hasSucceeded && currentIdx === {start_proxy_idx}) tryNext(); }}, 6000);
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
    session_id = None
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx:
            session_id = ctx.session_id
    except ImportError:
        pass
    
    vc.increment_visit(session_id)
    st.session_state.visited = True

# =====================================================================
# SIDEBAR
# =====================================================================

with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:0.3rem 0;'>"
        "<span style='font-size:1.2rem;'>📺</span> "
        "<span style='font-size:0.95rem;font-weight:600;color:#f1f5f9;'>M3U Editör Pro</span>"
        "</div>",
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
            except TimeoutError:
                st.error(f"⏱️ Zaman Aşımı ({REQUEST_TIMEOUT}s)")
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
                for col, default in [("LogoURL", ""), ("Tür", ""), ("Durum", "❔ Bekliyor")]:
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

    # Metrikler (filtrelenmiş veriye göre)
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("📺 Kanal", len(df_display))
    mc2.metric("📁 Grup", df_display["Grup"].nunique())
    hls_count = int((df_display["Tür"] == "HLS").sum()) if "Tür" in df_display.columns else 0
    mc3.metric("📡 HLS", hls_count)

    st.caption(f"Gösterilen: {len(df_display)} / {len(st.session_state.data)} kanal")

    # --- İşlemler Row ---
    m3u_out = convert_df_to_m3u(df_display)
    act1, act2, act3 = st.columns(3)
    with act1:
        st.download_button(
            label=f"📥 M3U İndir ({len(df_display)})",
            data=m3u_out,
            file_name="iptv_listesi.m3u",
            mime="text/plain",
            type="primary",
            use_container_width=True,
        )
    with act2:
        if st.button("🔗 M3U Link Oluştur", use_container_width=True):
            with st.spinner("Link oluşturuluyor..."):
                link = create_m3u_link(m3u_out)
            if link:
                st.session_state.m3u_link = link
                st.success("Link hazır!")
            else:
                st.error("Link oluşturulamadı.")
    with act3:
        if st.button("🔍 Sağlık Kontrolü", use_container_width=True):
            with st.spinner("Kanallar taranıyor..."):
                urls = df_display["URL"].tolist()
                results = batch_check_health(urls, max_workers=HEALTH_CHECK_MAX_WORKERS, timeout=HEALTH_CHECK_TIMEOUT)
                
                # Sadece filtrelenmiş veriyi değil, ana verideki ilgili URL'leri güncelle
                for i, url in enumerate(urls):
                    st.session_state.data.loc[st.session_state.data["URL"] == url, "Durum"] = results[i]
                st.rerun()

    if st.session_state.get("m3u_link"):
        st.code(st.session_state.m3u_link, language=None)
        st.caption("☝️ Bu linki IPTV oynatıcına yapıştırabilirsin.")

    # --- Canlı Oynatıcı ---
    st.markdown("### 🎬 Canlı Oynatıcı")
    
    # Seçenekleri "Durum - Kanal Adı" formatında hazırla
    play_options_map = {}
    for _, row in df_display.iterrows():
        durum = row.get("Durum", "").split(" ")[0] if "Durum" in row else "❔"
        display_name = f"{durum} {row['Kanal Adı']}"
        play_options_map[display_name] = row['Kanal Adı']
        
    play_name_display = st.selectbox(
        "Oynatılacak Kanal", 
        options=["Seçiniz..."] + list(play_options_map.keys()),
        index=0,
        key="play_select_auto"
    )

    if play_name_display != "Seçiniz...":
        real_name = play_options_map[play_name_display]
        current_playing = st.session_state.get("play_channel", {})
        
        # Eğer zaten bu kanal oynamıyorsa state'i güncelle
        if not current_playing or current_playing.get("name") != real_name:
            row = df_display[df_display["Kanal Adı"] == real_name]
            if not row.empty:
                st.session_state.play_channel = {
                    "name": real_name,
                    "url": row.iloc[0]["URL"],
                    "logo": row.iloc[0].get("LogoURL", ""),
                    "group": row.iloc[0].get("Grup", ""),
                    "durum": row.iloc[0].get("Durum", ""),
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
            if "CORS" in pc.get("durum", ""):
                st.warning("⚠️ CORS Kısıtlı Kanal: Proxy kullanılıyor.")
        with pcol2:
            st.markdown(f"### ▶ {pc['name']}")
            cors_restricted = "CORS" in pc.get("durum", "")
            components.html(render_live_player(pc["url"], height=380, cors_restricted=cors_restricted), height=420)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⏹ Durdur", use_container_width=True):
                st.session_state.play_channel = None
                st.rerun()
        with col2:
            # Tek kanal için M3U oluştur (Harici oynatıcılar için en garanti yöntem)
            single_m3u = f"#EXTM3U\n#EXTINF:-1,{pc['name']}\n{pc['url']}"
            st.download_button(
                "📥 Harici Oynatıcı (M3U)", 
                data=single_m3u, 
                file_name=f"{pc['name']}.m3u", 
                type="secondary", 
                use_container_width=True,
                help="VLC veya PotPlayer ile açmak için bu dosyayı indirin ve tıklayın."
            )
        st.markdown("---")

    # --- Kanal Tablosu ---
    display_cols = [c for c in ["Durum", "Grup", "Kanal Adı", "URL", "Tür"] if c in df_display.columns]
    st.dataframe(
        df_display[display_cols] if display_cols else df_display,
        use_container_width=True, hide_index=True, height=TABLE_HEIGHT,
        column_config={
            "URL": st.column_config.TextColumn("URL", width="large"),
            "Tür": st.column_config.TextColumn("Tür", width="small"),
            "Durum": st.column_config.TextColumn("Durum", width="small"),
        },
    )

else:
    st.markdown(
        "<div style='text-align:center;padding:80px 20px;'>"
        f"<div style='font-size:4rem;margin-bottom:1rem;'>{PAGE_ICON}</div>"
        f"<h2 style='color:#f1f5f9;'>{PAGE_TITLE}</h2>"
        f"<p style='color:#94a3b8;font-size:1.1rem;max-width:500px;margin:1rem auto;'>"
        f"Sol menüden bir M3U linki yapıştırın ve TR kanallarını kolayca filtreleyin.</p>"
        "</div>",
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
