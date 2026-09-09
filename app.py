import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import urllib.error
import io
import html
import os
import sys
import time
import logging
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
        APP_VERSION, HEALTH_CHECK_MAX_WORKERS, HEALTH_CHECK_TIMEOUT,
        HEALTH_CHECK_MAX_CHANNELS, USER_AGENT_PROFILES, DEFAULT_UPSTREAM_PROXY,
    )
except ImportError:
    PAGE_TITLE = "M3U Editör Pro"
    PAGE_ICON = "📺"
    REQUEST_TIMEOUT = 30
    USER_AGENT = "Mozilla/5.0"
    DEFAULT_TR_FILTER = True
    TABLE_HEIGHT = 600
    DISABLE_SSL_VERIFY = True
    APP_VERSION = "2.1.0"
    HEALTH_CHECK_MAX_WORKERS = 30
    HEALTH_CHECK_TIMEOUT = 3
    HEALTH_CHECK_MAX_CHANNELS = 50
    USER_AGENT_PROFILES = {"Standart (Tarayıcı)": "Mozilla/5.0"}
    DEFAULT_UPSTREAM_PROXY = ""

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
from utils.parser import (
    parse_m3u_lines, filter_channels, convert_df_to_m3u,
    convert_df_to_proxied_m3u, convert_df_to_csv,
    convert_df_to_json, convert_df_to_txt, batch_check_health,
)
from utils import network as network_utils
from utils.visitor_counter import VisitorCounter
from utils.proxy_server import LocalProxyServer

@st.cache_resource
def get_proxy_server():
    server = LocalProxyServer()
    server.start()
    return server

# --- CSS ---
def _load_css():
    css_path = os.path.join(current_dir, "static", "styles.css")
    try:
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except OSError:
        pass

_load_css()


# --- SİSTEMLER ---
vc = VisitorCounter()


# =====================================================================
# YARDIMCI FONKSİYONLAR
# =====================================================================

def _safe_contains(series: pd.Series, term: str) -> pd.Series:
    return series.astype(str).str.contains(term, case=False, na=False, regex=False)


def _ensure_channel_columns(df: pd.DataFrame) -> pd.DataFrame:
    for column_name, default_value in [("LogoURL", ""), ("Tür", ""), ("Durum", "❔ Bekliyor")]:
        if column_name not in df.columns:
            df[column_name] = default_value
    return df


def create_m3u_link(m3u_content: str) -> str:
    """Backward-compatible wrapper around the shared network helper."""
    return network_utils.create_m3u_link(
        m3u_content,
        user_agent=USER_AGENT,
        disable_ssl_verify=DISABLE_SSL_VERIFY,
    )


def _status_counts(df: pd.DataFrame) -> dict[str, int]:
    statuses = df.get("Durum", pd.Series(dtype=str)).astype(str)
    return {
        "active": int(statuses.str.contains("✅", na=False).sum()),
        "vpn": int(statuses.str.contains("🌍", na=False).sum()),
        "error": int(statuses.str.contains("❌", na=False).sum()),
        "pending": int(statuses.str.contains("Bekliyor", na=False).sum()),
    }


def _status_style(value: str) -> str:
    status_text = str(value)
    if "✅" in status_text:
        return "color: #7dd3a7; font-weight: 700;"
    if "🌍" in status_text:
        return "color: #60a5fa; font-weight: 700;"
    if "❌" in status_text:
        return "color: #fda4af; font-weight: 700;"
    if "Bekliyor" in status_text:
        return "color: #fcd34d; font-weight: 700;"
    if "⚠" in status_text or "⏱" in status_text:
        return "color: #fdba74; font-weight: 700;"
    return "color: #cbd5e1; font-weight: 600;"



def render_live_player(stream_url: str, height: int = 420) -> str:
    url = (
        (stream_url or "")
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', '\\"')
        .replace("\r", "")
        .replace("\n", "")
    )
    h = str(height)

    # Yerel proxy base URL
    proxy_server = get_proxy_server()
    local_proxy_base = f"http://127.0.0.1:{proxy_server.port}/proxy?url="

    return f"""
    <link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet" />
    <link href="https://unpkg.com/@videojs/themes@1.0.1/dist/city/index.css" rel="stylesheet">
    <style>
        .player-wrap {{
            position: relative; width: 100%; height: {h}px; background: #000;
            border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.08);
        }}
        .video-js {{ width: 100%; height: 100%; }}
        .vjs-city .vjs-big-play-button {{
            left: 50% !important; top: 50% !important; transform: translate(-50%, -50%) !important;
            margin: 0 !important; width: 2.5em !important; height: 2.5em !important; border-radius: 50% !important;
        }}
        #ps {{
            position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
            z-index: 20; pointer-events: none; text-align: center; color: #fff;
        }}
        #ps.active {{ background: rgba(0,0,0,0.65); pointer-events: auto; }}
        #ps .box {{
            background: rgba(15,23,42,0.92); padding: 22px 32px; border-radius: 16px;
            font-size: 0.92rem; border: 1px solid rgba(255,255,255,0.15); backdrop-filter: blur(10px);
            max-width: 420px;
        }}
        .abtn {{
            display: inline-block; margin: 5px; padding: 10px 20px; border: none; border-radius: 8px;
            cursor: pointer; font-size: 0.82rem; font-weight: 600; color: #fff; text-decoration: none;
        }}
        .abtn-blue {{ background: #3b82f6; }}
        .abtn-green {{ background: #10b981; }}
        .abtn-red {{ background: #ef4444; }}
        .abtn-gray {{ background: #475569; }}
    </style>

    <div class="player-wrap">
        <video id="vp" class="video-js vjs-theme-city vjs-big-play-centered"></video>
        <div id="ps"><div class="box" id="psb"><div id="pst">⏳ Başlatılıyor...</div></div></div>
    </div>

    <script src="https://vjs.zencdn.net/8.10.0/video.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.7"></script>
    <script src="https://cdn.jsdelivr.net/npm/mpegts.js@latest/dist/mpegts.js"></script>

    <script>
    (function(){{
        var origUrl = '{url}';
        if (!origUrl) return;

        var player = videojs('vp', {{
            autoplay:true, controls:true, responsive:true, fluid:false,
            liveui:true, preload:'auto', userActions:{{hotkeys:true}}
        }});

        var ps  = document.getElementById('ps');
        var pst = document.getElementById('pst');
        var ok  = false;
        var curHls = null;
        var curTs  = null;

        /* ── Proxy zinciri ── */
        var PROXIES = [
            {{ name:'Doğrudan',    fn: null }},
            {{ name:'Yerel Proxy', fn: function(u){{ return '{local_proxy_base}' + encodeURIComponent(u); }} }},
            {{ name:'AllOrigins',  fn: function(u){{ return 'https://api.allorigins.win/raw?url=' + encodeURIComponent(u); }} }},
            {{ name:'CorsProxy',   fn: function(u){{ return 'https://corsproxy.io/?' + encodeURIComponent(u); }} }},
            {{ name:'CodeTabs',    fn: function(u){{ return 'https://api.codetabs.com/v1/proxy?quest=' + encodeURIComponent(u); }} }}
        ];

        function log(m) {{
            console.log('[IPTV]', m);
        }}
        function show(m, lock) {{
            pst.innerHTML = m;
            ps.style.display = 'flex';
            ps.classList.toggle('active', !!lock);
        }}
        function hide() {{ ps.style.display = 'none'; }}

        function cleanup() {{
            if(curHls) {{ try{{curHls.destroy();}}catch(e){{}} curHls=null; }}
            if(curTs)  {{ try{{curTs.unload();curTs.detachMediaElement();curTs.destroy();}}catch(e){{}} curTs=null; }}
        }}

        var mediaEl = player.tech({{IWillNotUseThisInPlugins:true}}).el();

        /* ══════════════════════════════════════
           ANA DENEME FONKSİYONU
           ══════════════════════════════════════ */
        function tryAttempt(idx) {{
            if (ok || idx >= PROXIES.length) {{
                if (!ok) showFail();
                return;
            }}

            cleanup();
            var p = PROXIES[idx];
            log('▶ Deneme ' + idx + ': ' + p.name);
            show('🔄 ' + p.name + ' deneniyor...', false);

            var lower = origUrl.toLowerCase();
            var isHLS = lower.indexOf('.m3u8') !== -1 || lower.indexOf('m3u8') !== -1 
                     || lower.indexOf('/live/') !== -1 || lower.indexOf('/hls') !== -1
                     || lower.indexOf('playlist') !== -1;
            var isTS  = lower.indexOf('.ts') !== -1 && !isHLS;

            /* ── HLS Oynatma ── */
            if (typeof Hls !== 'undefined' && Hls.isSupported() && (isHLS || !isTS)) {{
                var cfg = {{
                    enableWorker: true,
                    lowLatencyMode: true,
                    manifestLoadingTimeOut: 8000,
                    fragLoadingTimeOut: 10000,
                    levelLoadingTimeOut: 8000,
                }};

                /*
                 * ✅ KRİTİK FİX: xhrSetup ile proxy
                 * loadSource() HER ZAMAN orijinal URL ile çağrılır.
                 * HLS.js relative URL'leri orijinal base'e göre çözümler.
                 * xhrSetup sadece gerçek HTTP isteğini proxy'den geçirir.
                 */
                if (p.fn) {{
                    cfg.xhrSetup = function(xhr, url) {{
                        var proxied = p.fn(url);
                        log('  → ' + url.substring(0,50) + '...');
                        xhr.open('GET', proxied, true);
                    }};
                }}

                var hls = new Hls(cfg);
                curHls = hls;

                /* ✅ HER ZAMAN orijinal URL! Proxy değil! */
                hls.loadSource(origUrl);
                hls.attachMedia(mediaEl);

                var tout = setTimeout(function() {{
                    if (!ok) {{
                        log('⏱ Timeout (' + p.name + ')');
                        tryAttempt(idx + 1);
                    }}
                }}, 12000);

                hls.on(Hls.Events.MANIFEST_PARSED, function(e, d) {{
                    clearTimeout(tout);
                    log('✅ Manifest OK! (' + d.levels.length + ' level)');
                    ok = true;
                    hide();
                    mediaEl.play().catch(function(err) {{
                        show('▶️ Oynatmak için tıklayın', false);
                        mediaEl.addEventListener('click', function() {{
                            mediaEl.play(); hide();
                        }}, {{once:true}});
                    }});
                }});

                hls.on(Hls.Events.FRAG_LOADED, function() {{
                    if (!ok) {{ clearTimeout(tout); ok = true; hide(); }}
                }});

                hls.on(Hls.Events.ERROR, function(e, d) {{
                    log('⚠ HLS: ' + d.details + ' fatal=' + d.fatal);
                    if (d.fatal) {{
                        clearTimeout(tout);
                        tryAttempt(idx + 1);
                    }}
                }});

                return;
            }}

            /* ── MPEG-TS ── */
            if (isTS && typeof mpegts !== 'undefined' && mpegts.isSupported()) {{
                var tsUrl = p.fn ? p.fn(origUrl) : origUrl;
                log('TS: ' + tsUrl.substring(0,60));
                var m = mpegts.createPlayer({{type:'mpegts', url:tsUrl, isLive:true}});
                curTs = m;
                m.attachMediaElement(mediaEl);
                m.load(); m.play();
                var ttout = setTimeout(function(){{ if(!ok) tryAttempt(idx+1); }}, 10000);
                m.on(mpegts.Events.ERROR, function(){{ clearTimeout(ttout); tryAttempt(idx+1); }});
                mediaEl.addEventListener('playing', function(){{
                    clearTimeout(ttout); ok=true; hide();
                }}, {{once:true}});
                return;
            }}

            /* ── Genel Video ── */
            var vUrl = p.fn ? p.fn(origUrl) : origUrl;
            player.src({{src:vUrl, type:'video/mp4'}});
            var dtout = setTimeout(function(){{ if(!ok) tryAttempt(idx+1); }}, 8000);
            player.one('playing', function(){{ clearTimeout(dtout); ok=true; hide(); }});
            player.one('error', function(){{ clearTimeout(dtout); tryAttempt(idx+1); }});
            player.play().catch(function(){{}});
        }}

        function copyToClipboard(text, btn) {{
            if (navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(text).then(function() {{
                    if (btn) btn.textContent = '✅ Kopyalandı!';
                }}).catch(function() {{
                    legacyCopy(text, btn);
                }});
            }} else {{
                legacyCopy(text, btn);
            }}
        }}
        function legacyCopy(text, btn) {{
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            try {{
                document.execCommand('copy');
                if (btn) btn.textContent = '✅ Kopyalandı!';
            }} catch(e) {{
                if (btn) btn.textContent = '❌ Kopyalanamadı';
            }}
            document.body.removeChild(ta);
        }}

        /* ── Başarısız UI ── */
        function showFail() {{
            log('❌ Tüm yöntemler başarısız');
            show(
                '🚫 Oynatılamadı<br>' +
                '<p style="font-size:0.75rem;color:#94a3b8;margin:5px 0 12px 0;">' +
                'Bu kanal tarayıcıda CORS, DRM veya <b>Bölgesel Kısıtlama (VPN)</b> nedeniyle açılamıyor olabilir.<br>' +
                'Harici oynatıcı (VLC/TiviMate) kullanın veya proxy/VPN tüneli aktifleştirin.</p>' +
                '<button class="abtn abtn-blue" onclick="location.reload()">🔄 Tekrar</button>' +
                '<button class="abtn abtn-green" onclick="copyToClipboard(\\'' + origUrl + '\\', this)">📋 URL Kopyala</button><br>' +
                '<div style="margin-top:10px;border-top:1px solid rgba(255,255,255,0.1);padding-top:10px;">' +
                '<a href="vlc://' + origUrl + '" class="abtn abtn-red">▶ VLC</a>' +
                '<a href="potplayer://' + origUrl + '" class="abtn abtn-gray">▶ PotPlayer</a></div>',
                true
            );
        }}

        /* ── Global hata yakalama ── */
        player.on('playing', function(){{ ok=true; hide(); }});
        player.on('error', function(){{ if(!ok) log('VideoJS error: ' + JSON.stringify(player.error())); }});

        /* ══ BAŞLAT ══ */
        log('URL: ' + origUrl);
        tryAttempt(0);
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
if "recent_urls" not in st.session_state:
    st.session_state.recent_urls = []
if "upstream_proxy" not in st.session_state:
    st.session_state.upstream_proxy = DEFAULT_UPSTREAM_PROXY
if "selected_ua_profile" not in st.session_state:
    st.session_state.selected_ua_profile = "Standart (Tarayıcı)"
if "custom_referer" not in st.session_state:
    st.session_state.custom_referer = ""
if "show_add_channel" not in st.session_state:
    st.session_state.show_add_channel = False

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
        "<div class='sidebar-brand'>"
        "<span class='sidebar-brand__icon'>📺</span>"
        "<div>"
        "<span class='sidebar-brand__title'>M3U Editör Pro</span>"
        "<span class='sidebar-brand__subtitle'>Yükle, filtrele, oynat</span>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # 🌍 Yurt Dışı & VPN Çözümleri Paneli
    with st.expander("🌍 Yurt Dışı & VPN Çözümleri", expanded=bool(st.session_state.upstream_proxy)):
        st.caption("Yurt dışı kaynaklı veya bölge kısıtlamalı IPTV akışları için proxy tüneli ve kimlik ayarları:")
        cfg_proxy = st.text_input(
            "Proxy / VPN Tüneli (HTTP/SOCKS):",
            value=st.session_state.upstream_proxy,
            placeholder="http://127.0.0.1:10808 veya http://proxy:port",
            help="Yerel VPN istemcinizin (Clash, v2ray, xray vb.) veya harici proxy sunucunuzun adresi. Tanımlandığında tüm akışlar ve taramalar buradan tünellenir.",
            key="cfg_proxy_input",
        )
        profile_list = list(USER_AGENT_PROFILES.keys())
        p_index = profile_list.index(st.session_state.selected_ua_profile) if st.session_state.selected_ua_profile in profile_list else 0
        cfg_profile = st.selectbox(
            "Oynatıcı / Cihaz Profili (User-Agent):",
            profile_list,
            index=p_index,
            help="Birçok yabancı IPTV sunucusu tarayıcıları engeller (403 Forbidden). TiviMate veya VLC seçerek kimlik engelini aşabilirsiniz.",
            key="cfg_profile_select",
        )
        cfg_ref = st.text_input(
            "Özel Referer Başlığı (Opsiyonel):",
            value=st.session_state.custom_referer,
            placeholder="Örn: https://iptv-provider.com",
            help="Yayıncı sunucu sadece kendi web sitesinden gelen isteklere izin veriyorsa doldurun.",
            key="cfg_ref_input",
        )

        st.session_state.upstream_proxy = cfg_proxy.strip()
        st.session_state.selected_ua_profile = cfg_profile
        st.session_state.custom_referer = cfg_ref.strip()

        active_ua = USER_AGENT_PROFILES.get(cfg_profile, USER_AGENT)
        get_proxy_server().set_proxy_config(
            upstream_proxy=st.session_state.upstream_proxy,
            custom_user_agent=active_ua,
            custom_referer=st.session_state.custom_referer,
        )

        if st.session_state.upstream_proxy:
            st.success("🟢 Proxy Tüneli Aktif")
        else:
            st.info("⚪ Doğrudan Bağlantı")

    st.markdown("---")

    # Son kullanılan linkler geçmişi
    default_url_val = ""
    if st.session_state.recent_urls:
        chosen_recent = st.selectbox(
            "🕒 Son Kullanılan Linkler:",
            ["(Yeni Link Girin...)"] + st.session_state.recent_urls,
            key="recent_url_selector",
        )
        if chosen_recent != "(Yeni Link Girin...)":
            default_url_val = chosen_recent

    url = st.text_input("🌐 M3U Linki Yapıştır:", value=default_url_val)
    uploaded_file = st.file_uploader("📂 veya M3U Dosyası Yükle", type=["m3u", "m3u8"])
    only_tr = st.checkbox("🇹🇷 Sadece TR Kanalları", value=DEFAULT_TR_FILTER)

    if st.button("🚀 Listeyi Çek ve Tara", use_container_width=True, type="primary"):
        # Belleği hemen boşaltmak için eski verileri temizle
        st.session_state.data = pd.DataFrame()
        import gc
        gc.collect()

        source_lines = None
        start = time.time()
        if url:
            try:
                with st.spinner("Link indiriliyor..."):
                    active_ua = USER_AGENT_PROFILES.get(st.session_state.selected_ua_profile, USER_AGENT)
                    req_headers = {}
                    if st.session_state.custom_referer:
                        req_headers["Referer"] = st.session_state.custom_referer

                    source_lines = network_utils.fetch_m3u_source(
                        url,
                        user_agent=active_ua,
                        timeout=REQUEST_TIMEOUT,
                        disable_ssl_verify=DISABLE_SSL_VERIFY,
                        proxy_url=st.session_state.upstream_proxy or None,
                        headers=req_headers or None,
                    )
                    # Başarılı ise son kullanılan linklere ekle
                    if url and url not in st.session_state.recent_urls:
                        st.session_state.recent_urls.insert(0, url)
                        st.session_state.recent_urls = st.session_state.recent_urls[:5]
            except urllib.error.HTTPError as e:
                if e.code in (403, 451):
                    st.error(f"🚫 HTTP {e.code}: Bölgesel Kısıtlama / VPN Gerekli!")
                else:
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
            source_lines = None
            gc.collect()

            filtered = filter_channels(raw, only_tr)
            raw = None
            gc.collect()

            elapsed = round(time.time() - start, 2)
            if filtered:
                df = _ensure_channel_columns(pd.DataFrame(filtered))
                filtered = None
                gc.collect()

                st.session_state.data = df
                st.session_state.play_channel = None  # ✅ Yeni liste yüklendiğinde eski oynatmayı sıfırla
                st.success(f"✅ {len(df)} kanal bulundu ({elapsed}s)")
            else:
                st.warning("⚠️ Kanal bulunamadı.")

    st.markdown("---")

    # Filtreler
    selected_groups = []
    selected_types = []
    selected_statuses = []
    if not st.session_state.data.empty:
        st.markdown("#### ⚙️ Filtre")
        try:
            group_options = sorted(st.session_state.data["Grup"].astype(str).dropna().unique())
        except Exception:
            group_options = []
        if group_options:
            selected_groups = st.multiselect("Grupları filtrele", group_options, default=None, key="group_filter")

        type_options = sorted(st.session_state.data.get("Tür", pd.Series(dtype=str)).astype(str).dropna().unique())
        if type_options:
            selected_types = st.multiselect("Yayın türü", type_options, default=None, key="type_filter")
        status_options = sorted(st.session_state.data.get("Durum", pd.Series(dtype=str)).astype(str).dropna().unique())
        if status_options:
            selected_statuses = st.multiselect("Duruma göre", status_options, default=None, key="status_filter")

    # İstatistikler
    st.markdown("---")

    stats = vc.get_stats()
    st.markdown(f"**👥 Toplam Ziyaret:** {stats['total_visits']}")
    st.markdown(f"**👤 Tekil Ziyaretçi:** {stats['unique_visitors']}")
    try:
        last_visit = datetime.fromisoformat(stats['last_visit']).strftime("%d.%m.%Y %H:%M")
    except (ValueError, KeyError):
        last_visit = "—"
    st.caption(f"Son Ziyaret: {last_visit}")

# =====================================================================
# ANA EKRAN
# =====================================================================

if not st.session_state.data.empty:
    # Filtreleme
    df_display = st.session_state.data.copy()
    if selected_groups:
        df_display = df_display[df_display["Grup"].isin(selected_groups)]
    if selected_types:
        df_display = df_display[df_display["Tür"].isin(selected_types)]
    if selected_statuses:
        df_display = df_display[df_display["Durum"].isin(selected_statuses)]

    st.markdown(
        f"""
        <div class="page-header fade-in">
            <h1>{PAGE_ICON} {html.escape(PAGE_TITLE)}</h1>
            <p>Kanalları filtreleyin, sağlık kontrolü yapın ve doğrudan oynatın.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    search_term = st.text_input("🔍 Kanal Ara:", "", placeholder="Kanal adı veya grup yazın...")
    if search_term:
        df_display = df_display[
            _safe_contains(df_display["Kanal Adı"], search_term)
            | _safe_contains(df_display["Grup"], search_term)
        ]

    status_counts = _status_counts(df_display)
    group_count = df_display["Grup"].nunique()
    hls_count = int((df_display["Tür"] == "HLS").sum()) if "Tür" in df_display.columns else 0

    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    mc1.metric("📺 Görünen", len(df_display))
    mc2.metric("📁 Grup", group_count)
    mc3.metric("🟢 Aktif", status_counts["active"])
    mc4.metric("🌍 VPN Gerekli", status_counts["vpn"])
    mc5.metric("📡 HLS", hls_count)
    st.caption(f"Gösterilen: {len(df_display)} / {len(st.session_state.data)} kanal")

    active_filters = []
    if search_term:
        active_filters.append(f"Arama: {search_term}")
    active_filters.extend(f"Grup: {value}" for value in selected_groups)
    active_filters.extend(f"Tür: {value}" for value in selected_types)
    active_filters.extend(f"Durum: {value}" for value in selected_statuses)
    summary_text = " • ".join(active_filters) if active_filters else "Tüm kanallar gösteriliyor"
    st.markdown(
        f"<div class='simple-strip'><strong>Filtreler</strong><span>{html.escape(summary_text)}</span></div>",
        unsafe_allow_html=True,
    )

    # =====================================================================
    # HIZLI İŞLEMLER & SAĞLIK KONTROLÜ
    # =====================================================================
    st.markdown("### ⚡ Hızlı İşlemler")
    act_col1, act_col2, act_col3, act_col4 = st.columns(4)

    with act_col1:
        health_limit_options = [50, 100, 250, 500, "Tümü"]
        h_limit = st.selectbox(
            "Taranacak Kanal Sayısı",
            health_limit_options,
            index=0,
            label_visibility="collapsed",
            key="h_limit_sel"
        )
        if st.button("🔍 Sağlık Kontrolü", use_container_width=True, type="primary"):
            max_health = len(df_display) if h_limit == "Tümü" else int(h_limit)
            urls = df_display["URL"].head(max_health).tolist()
            total = len(urls)
            if len(df_display) > total:
                st.info(f"Sağlık kontrolü ilk {total} kanal ile sınırlandı.")

            progress_bar = st.progress(0, text=f"🔍 Taranıyor... 0/{total}")
            status_text = st.empty()
            start_time = time.time()

            def update_progress(completed, total_count):
                pct = completed / total_count
                elapsed = time.time() - start_time
                speed = completed / elapsed if elapsed > 0 else 0
                remaining = (total_count - completed) / speed if speed > 0 else 0
                progress_bar.progress(
                    pct, 
                    text=f"🔍 {completed}/{total_count} — {pct:.0%} | ⏱️ ~{remaining:.0f}s kaldı"
                )

            active_ua = USER_AGENT_PROFILES.get(st.session_state.selected_ua_profile, USER_AGENT)
            extra_headers = {"Referer": st.session_state.custom_referer} if st.session_state.custom_referer else None

            results = batch_check_health(
                urls, 
                max_workers=HEALTH_CHECK_MAX_WORKERS,
                timeout=HEALTH_CHECK_TIMEOUT,
                user_agent=active_ua,
                proxy_url=st.session_state.upstream_proxy or None,
                headers=extra_headers,
                progress_callback=update_progress
            )

            elapsed = round(time.time() - start_time, 1)

            # Sonuçları ana veriye yaz
            for i, u in enumerate(urls):
                st.session_state.data.loc[st.session_state.data["URL"] == u, "Durum"] = results[i]

            aktif = sum(1 for r in results if "✅" in r)
            vpn_cnt = sum(1 for r in results if "🌍" in r)
            oldu = sum(1 for r in results if "❌" in r)
            diger = total - aktif - vpn_cnt - oldu

            progress_bar.empty()
            status_text.empty()
            st.success(
                f"✅ Tamamlandı ({elapsed}s) — "
                f"🟢 {aktif} aktif | 🌍 {vpn_cnt} VPN gerekli | 🔴 {oldu} ölü | 🟡 {diger} belirsiz"
            )
            time.sleep(1.5)
            st.rerun()

    with act_col2:
        has_dead = bool((st.session_state.data["Durum"].astype(str).str.contains("❌|⏱️|Geçersiz|Bulunamadı", na=False)).any())
        if st.button("🧹 Ölü Kanalları Temizle", use_container_width=True, disabled=not has_dead, help="❌ veya ⏱️ durumundaki kanalları listeden çıkarır."):
            before_len = len(st.session_state.data)
            st.session_state.data = st.session_state.data[
                ~st.session_state.data["Durum"].astype(str).str.contains("❌|⏱️|Geçersiz|Bulunamadı", na=False)
            ].reset_index(drop=True)
            removed = before_len - len(st.session_state.data)
            st.toast(f"🧹 {removed} adet çalışmayan kanal temizlendi!", icon="✅")
            st.rerun()

    with act_col3:
        has_active = bool((st.session_state.data["Durum"].astype(str).str.contains("✅", na=False)).any())
        if st.button("⭐ Sadece Çalışanları Tut", use_container_width=True, disabled=not has_active, help="Yalnızca '✅ Aktif' olan kanalları korur."):
            before_len = len(st.session_state.data)
            st.session_state.data = st.session_state.data[
                st.session_state.data["Durum"].astype(str).str.contains("✅", na=False)
            ].reset_index(drop=True)
            st.toast(f"⭐ Sadece {len(st.session_state.data)} aktif kanal korundu!", icon="⭐")
            st.rerun()

    with act_col4:
        if st.button("➕ Yeni Kanal Ekle", use_container_width=True):
            st.session_state.show_add_channel = not st.session_state.get("show_add_channel", False)
            st.rerun()

    # Yeni Kanal Ekle Formu
    if st.session_state.get("show_add_channel"):
        with st.container():
            st.markdown("#### ➕ Yeni Kanal Ekle")
            with st.form("new_channel_form", clear_on_submit=True):
                c_col1, c_col2 = st.columns(2)
                with c_col1:
                    add_name = st.text_input("Kanal Adı *")
                    add_group = st.text_input("Grup *", value="Genel")
                with c_col2:
                    add_url = st.text_input("Akış (Stream) URL *")
                    add_logo = st.text_input("Logo URL (Opsiyonel)")
                sub1, sub2 = st.columns([1, 4])
                with sub1:
                    submit_add = st.form_submit_button("Listeye Ekle", type="primary", use_container_width=True)
                with sub2:
                    cancel_add = st.form_submit_button("Vazgeç / Kapat")

                if submit_add:
                    if not add_name.strip() or not add_url.strip():
                        st.error("Kanal Adı ve Akış URL zorunludur!")
                    else:
                        add_type = "HLS" if (".m3u8" in add_url.lower() or "/live/" in add_url.lower()) else "Diğer"
                        new_row = pd.DataFrame([{
                            "Kanal Adı": add_name.strip(),
                            "Grup": add_group.strip() or "Genel",
                            "URL": add_url.strip(),
                            "LogoURL": add_logo.strip(),
                            "Tür": add_type,
                            "Durum": "❔ Bekliyor",
                        }])
                        st.session_state.data = pd.concat([new_row, st.session_state.data], ignore_index=True)
                        st.session_state.show_add_channel = False
                        st.success(f"✅ '{add_name}' kanalı listeye eklendi!")
                        st.rerun()
                elif cancel_add:
                    st.session_state.show_add_channel = False
                    st.rerun()

    # =====================================================================
    # DIŞA AKTARMA & PAYLAŞIM MERKEZİ
    # =====================================================================
    st.markdown("### 📤 Dışa Aktarma & Paylaşım Merkezi")
    
    # Yerel ağ IP adresi tespiti
    import socket
    def _get_lan_ip():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    lan_ip = _get_lan_ip()
    proxy_server = get_proxy_server()
    lan_proxy_base = f"http://{lan_ip}:{proxy_server.port}/proxy"
    
    m3u_standard = convert_df_to_m3u(df_display)
    m3u_proxied = convert_df_to_proxied_m3u(df_display, lan_proxy_base)
    
    # Yerel proxy sunucusuna çalma listelerini yaz
    proxy_server.set_m3u_content(m3u_standard, proxied_content=m3u_proxied)

    tab_m3u, tab_vpn_bridge, tab_data, tab_share = st.tabs([
        "📥 M3U / M3U8 İndir",
        "🌍 Smart TV / VPN Köprüsü M3U",
        "📊 CSV & JSON & TXT",
        "🔗 Canlı Link Paylaşımı",
    ])

    with tab_m3u:
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            st.download_button(
                label=f"📥 Standart M3U İndir ({len(df_display)} Kanal)",
                data=m3u_standard,
                file_name="iptv_listesi.m3u",
                mime="text/plain",
                type="primary",
                use_container_width=True,
            )
        with exp_col2:
            st.download_button(
                label=f"📥 Genişletilmiş M3U8 İndir ({len(df_display)} Kanal)",
                data=m3u_standard,
                file_name="iptv_listesi.m3u8",
                mime="application/x-mpegURL",
                use_container_width=True,
            )

    with tab_vpn_bridge:
        st.info(
            "💡 **Smart TV & Harici Cihazlar İçin VPN Köprüsü:**\n\n"
            "Smart TV, Android Box veya mobil cihazınızda VPN kurulu değilse bu seçeneği kullanın! "
            "Bu M3U listesindeki tüm akışlar bilgisayarınızın yerel proxy sunucusu üzerinden tünellenir. "
            "Bilgisayarınız açık olduğu ve VPN'e/Proxy'ye bağlı olduğu sürece, TV'niz de tüm yurt dışı kanalları kesintisiz izleyebilir."
        )
        vcol1, vcol2 = st.columns(2)
        with vcol1:
            st.download_button(
                label="🌍 VPN Köprüsü M3U Dosyası İndir",
                data=m3u_proxied,
                file_name="vpn_koprusu_listesi.m3u",
                mime="text/plain",
                type="primary",
                use_container_width=True,
                help="Smart TV'nize aktarmak için indirin.",
            )
        with vcol2:
            proxied_lan_url = f"http://{lan_ip}:{proxy_server.port}/proxied_playlist.m3u"
            st.caption("Aynı Wi-Fi/Ağdaki Smart TV için doğrudan URL:")
            st.code(proxied_lan_url, language=None)

    with tab_data:
        dcol1, dcol2, dcol3 = st.columns(3)
        with dcol1:
            st.download_button(
                label="📊 Excel / CSV İndir",
                data=convert_df_to_csv(df_display),
                file_name="iptv_kanallar.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with dcol2:
            st.download_button(
                label="📦 JSON Formatında İndir",
                data=convert_df_to_json(df_display),
                file_name="iptv_kanallar.json",
                mime="application/json",
                use_container_width=True,
            )
        with dcol3:
            st.download_button(
                label="📄 TXT (Ham URL Listesi)",
                data=convert_df_to_txt(df_display),
                file_name="iptv_linkler.txt",
                mime="text/plain",
                use_container_width=True,
            )

    with tab_share:
        sh_btn = st.button("🚀 İnternet Paylaşım Linki Oluştur (termbin.com)", use_container_width=True)
        if sh_btn or st.session_state.get("m3u_cloud_link"):
            if sh_btn:
                with st.spinner("Bulut linki üretiliyor..."):
                    st.session_state.m3u_cloud_link = network_utils.create_m3u_link(
                        m3u_standard,
                        user_agent=USER_AGENT,
                        disable_ssl_verify=DISABLE_SSL_VERIFY,
                    )
            if st.session_state.get("m3u_cloud_link"):
                st.success("İnternet üzerinden (dış ağlar, mobil, uzaktaki TV vb.) erişilecek doğrudan link:")
                st.code(st.session_state.m3u_cloud_link, language=None)
            else:
                st.error("Bulut linki oluşturulamadı. İnternet bağlantınızı kontrol edin.")

        st.caption("Aynı Wi-Fi/Ağdaki Oynatıcılar için Yerel M3U Bağlantısı:")
        st.code(f"http://{lan_ip}:{proxy_server.port}/playlist.m3u", language=None)

    # =====================================================================
    # CANLI OYNATICI
    # =====================================================================
    st.markdown("### 🎬 Canlı Oynatıcı")

    play_options = []
    play_url_map = {}

    for idx, row in df_display.iterrows():
        durum = row.get("Durum", "❔").split(" ")[0] if "Durum" in row else "❔"
        base_name = f"{durum} {row['Kanal Adı']}"

        display_name = base_name
        counter = 2
        while display_name in play_url_map:
            display_name = f"{base_name} ({counter})"
            counter += 1

        play_options.append(display_name)
        play_url_map[display_name] = {
            "name": row["Kanal Adı"],
            "url": row["URL"],
            "logo": row.get("LogoURL", ""),
            "group": row.get("Grup", ""),
            "durum": row.get("Durum", ""),
        }

    current_play = st.session_state.get("play_channel")
    default_index = 0
    if current_play:
        for i, opt in enumerate(play_options):
            info = play_url_map[opt]
            if info["name"] == current_play.get("name") and info["url"] == current_play.get("url"):
                default_index = i + 1
                break

    play_name_display = st.selectbox(
        "Oynatılacak Kanal",
        options=["Seçiniz..."] + play_options,
        index=default_index,
        key="play_select_auto"
    )

    if play_name_display != "Seçiniz...":
        selected_info = play_url_map.get(play_name_display)
        if selected_info:
            current = st.session_state.get("play_channel")
            if not current or current.get("url") != selected_info["url"] or current.get("name") != selected_info["name"]:
                st.session_state.play_channel = selected_info
                st.rerun()
    else:
        if st.session_state.play_channel:
            st.session_state.play_channel = None
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
            st.markdown(
                f"<span style='color:#94a3b8;'>Grup:</span> "
                f"<span style='color:#f1f5f9;font-weight:600;'>{pc.get('group', '')}</span>",
                unsafe_allow_html=True,
            )
            if "VPN" in pc.get("durum", ""):
                st.warning("🌍 Bölge Kısıtlaması (VPN gerekebilir).")
            elif "CORS" in pc.get("durum", ""):
                st.info("⚠️ CORS Kısıtlı — Yerel proxy devrede.")
            
            st.caption("📋 Akış URL:")
            st.code(pc["url"], language=None)
            
        with pcol2:
            st.markdown(f"### ▶ {pc['name']}")
            components.html(
                render_live_player(pc["url"], height=380),
                height=420,
            )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⏹ Oynatmayı Durdur", use_container_width=True):
                st.session_state.play_channel = None
                st.rerun()
        with col2:
            single_m3u = f"#EXTM3U\n#EXTINF:-1,{pc['name']}\n{pc['url']}"
            st.download_button(
                "📥 Harici Oynatıcı İçin İndir (M3U)",
                data=single_m3u,
                file_name=f"{pc['name']}.m3u",
                type="secondary",
                use_container_width=True,
                help="VLC veya PotPlayer ile doğrudan açmak için indirin.",
            )
        st.markdown("---")

    # =====================================================================
    # KANAL TABLOSU & CANLI DÜZENLEME (DATA EDITOR)
    # =====================================================================
    st.markdown("### 📋 Kanal Tablosu & Canlı Düzenleme")
    st.caption("💡 Tablodaki hücrelere çift tıklayarak kanal adı, grup ve linkleri doğrudan düzenleyebilir veya satır silebilirsiniz.")

    display_cols = [c for c in ["Durum", "Grup", "Kanal Adı", "URL", "Tür"] if c in df_display.columns]
    table_df = df_display[display_cols] if display_cols else df_display

    edited_df = st.data_editor(
        table_df,
        use_container_width=True,
        hide_index=True,
        height=TABLE_HEIGHT,
        num_rows="dynamic",
        disabled=["Durum", "Tür"],
        key="channel_data_editor",
        column_config={
            "URL": st.column_config.TextColumn("URL", width="large"),
            "Tür": st.column_config.TextColumn("Tür", width="small"),
            "Durum": st.column_config.TextColumn("Durum", width="small"),
            "Grup": st.column_config.TextColumn("Grup", width="medium"),
            "Kanal Adı": st.column_config.TextColumn("Kanal Adı", width="medium"),
        },
    )

    # Değişiklikleri ana state'e senkronize etme butonu
    if st.button("💾 Tablodaki Değişiklikleri Kaydet", use_container_width=True):
        # Düzenlenen veriyi ana state ile birleştir
        st.session_state.data = edited_df
        st.success("✅ Kanal tablosundaki tüm düzenlemeler kaydedildi!")
        time.sleep(1)
        st.rerun()

    # =====================================================================
    # 🌍 YURT DIŞI & VPN ÇÖZÜM REHBERİ
    # =====================================================================
    with st.expander("🌍 Yurt Dışı & Bölgesel Kısıtlamalı (VPN) Kanallar İçin Çözüm Rehberi"):
        st.markdown("""
        #### Neden Bazı Kanallar Açılmaz veya Hata Verir?
        1. **Coğrafi / Ülke Kilidi (Geo-Block / HTTP 403-451):** Birçok yayıncı yalnızca belirli ülkelerin IP adreslerine izin verir (Örn: Almanya, İngiltere, ABD).
        2. **İnternet Servis Sağlayıcı (ISS) Engeli:** Türkiye'deki bazı servis sağlayıcılar IPTV sunucu IP'lerini filtreleyebilir.
        3. **Tarayıcı / User-Agent Koruması:** Sunucular standart web tarayıcılarını engeller ve sadece IPTV oynatıcılarına (VLC, TiviMate, Kodi) izin verir.

        ---
        #### Bu Sitede Sağlanan Çözümler:
        * **1. Çözüm (Cihaz / User-Agent Profili):** Sol menüdeki *'🌍 Yurt Dışı & VPN Çözümleri'* bölümünden profili **TiviMate** veya **VLC** olarak değiştirin. Çoğu kanal tarayıcı engelini hemen aşacaktır.
        * **2. Çözüm (Upstream Proxy Tüneli):** Bilgisayarınızda çalışan bir VPN istemciniz veya yurt dışı HTTP/SOCKS proxy'niz varsa adresini girin (örn: `http://127.0.0.1:10808`). Bu sitedeki tüm taramalar ve yerel proxy doğrudan o tünelden geçecektir.
        * **3. Çözüm (Smart TV / VPN Köprüsü):** Smart TV'nize VPN kuramıyorsanız, yukarıdaki *'🌍 Smart TV / VPN Köprüsü M3U'* sekmesindeki dosyayı indirin veya yerel linki TV'nize girin. TV'niz bu bilgisayar üzerinden yayınları çeker!
        * **4. Çözüm (Ücretsiz VPN Tavsiyesi):** Ücretsiz ve hızlı çözüm için bilgisayarınıza **Cloudflare WARP (1.1.1.1)** veya **ProtonVPN Free** kurabilirsiniz.
        """)

else:
    st.markdown(
        "<div class='empty-state fade-in'>"
        f"<div class='empty-state__icon'>{PAGE_ICON}</div>"
        f"<h2>{PAGE_TITLE}</h2>"
        "<p>Sol menüden bir M3U linki yapıştırın veya dosya yükleyin.</p>"
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
