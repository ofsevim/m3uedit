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
    
    # Ağ & Proxy mini durum göstergesi
    if st.session_state.upstream_proxy:
        st.markdown("<div style='margin:8px 0;padding:4px 8px;border-radius:8px;background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.3);font-size:0.78rem;color:#86efac;'>🟢 <b>VPN/Proxy Aktif</b></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='margin:8px 0;padding:4px 8px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);font-size:0.78rem;color:#94a3b8;'>⚪ <b>Doğrudan Bağlantı</b></div>", unsafe_allow_html=True)

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

    # Üst Başlık
    st.markdown(
        f"""
        <div class="page-header fade-in">
            <h1>{PAGE_ICON} {html.escape(PAGE_TITLE)}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    status_counts = _status_counts(df_display)
    group_count = df_display["Grup"].nunique()
    hls_count = int((df_display["Tür"] == "HLS").sum()) if "Tür" in df_display.columns else 0

    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    mc1.metric("📺 Görünen Kanal", f"{len(df_display)} / {len(st.session_state.data)}")
    mc2.metric("📁 Gruplar", group_count)
    mc3.metric("🟢 Aktif", status_counts["active"])
    mc4.metric("🌍 VPN Gerekli", status_counts["vpn"])
    mc5.metric("📡 HLS", hls_count)

    active_filters = []
    active_filters.extend(f"Grup: {value}" for value in selected_groups)
    active_filters.extend(f"Tür: {value}" for value in selected_types)
    active_filters.extend(f"Durum: {value}" for value in selected_statuses)
    if active_filters:
        st.markdown(
            f"<div class='simple-strip'><strong>Aktif Filtreler:</strong> <span>{' • '.join(active_filters)}</span></div>",
            unsafe_allow_html=True,
        )

    # 4 ANA ODAKLI SEKME
    tab_editor, tab_player, tab_export, tab_vpn = st.tabs([
        "📋 Kanallar & Düzenle",
        "🎬 Canlı Oynatıcı",
        "📤 Dışa Aktar & Paylaş",
        "🌍 VPN & Yurt Dışı Çözümleri",
    ])

    # =====================================================================
    # SEKME 1: KANALLAR & DÜZENLEME
    # =====================================================================
    with tab_editor:
        # Arama çubuğu
        search_term = st.text_input("🔍 Kanal veya Grup Ara:", "", placeholder="Kanal adı veya grup yazarak anında filtreleyin...", key="tab_search")
        if search_term:
            df_display = df_display[
                _safe_contains(df_display["Kanal Adı"], search_term)
                | _safe_contains(df_display["Grup"], search_term)
            ]

        # Hızlı Aksiyonlar
        st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
        act1, act2, act3, act4 = st.columns([2.4, 1.4, 1.4, 1.2])

        with act1:
            c_sel, c_btn = st.columns([1, 1.4])
            with c_sel:
                h_limit = st.selectbox(
                    "Tarama Limiti",
                    [50, 100, 250, 500, "Tümü"],
                    index=0,
                    label_visibility="collapsed",
                    key="h_limit_sel_editor",
                )
            with c_btn:
                run_health = st.button("🔍 Sağlık Kontrolü", use_container_width=True, type="primary")

        with act2:
            has_dead = bool((st.session_state.data["Durum"].astype(str).str.contains("❌|⏱️|Geçersiz|Bulunamadı", na=False)).any())
            clean_dead = st.button("🧹 Ölüleri Temizle", use_container_width=True, disabled=not has_dead, help="❌ ve ⏱️ durumundaki kanalları listeden çıkarır.")

        with act3:
            has_active = bool((st.session_state.data["Durum"].astype(str).str.contains("✅", na=False)).any())
            keep_active = st.button("⭐ Sadece Çalışanlar", use_container_width=True, disabled=not has_active, help="Yalnızca '✅ Aktif' kanalları korur.")

        with act4:
            toggle_add = st.button("➕ Kanal Ekle", use_container_width=True)

        if run_health:
            max_health = len(df_display) if h_limit == "Tümü" else int(h_limit)
            urls = df_display["URL"].head(max_health).tolist()
            total = len(urls)
            progress_bar = st.progress(0, text=f"🔍 Taranıyor... 0/{total}")
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
            for i, u in enumerate(urls):
                st.session_state.data.loc[st.session_state.data["URL"] == u, "Durum"] = results[i]

            aktif = sum(1 for r in results if "✅" in r)
            vpn_cnt = sum(1 for r in results if "🌍" in r)
            oldu = sum(1 for r in results if "❌" in r)
            diger = total - aktif - vpn_cnt - oldu
            progress_bar.empty()
            st.success(f"✅ Tamamlandı ({elapsed}s) — 🟢 {aktif} aktif | 🌍 {vpn_cnt} VPN gerekli | 🔴 {oldu} ölü | 🟡 {diger} belirsiz")
            time.sleep(1.2)
            st.rerun()

        if clean_dead:
            before_len = len(st.session_state.data)
            st.session_state.data = st.session_state.data[
                ~st.session_state.data["Durum"].astype(str).str.contains("❌|⏱️|Geçersiz|Bulunamadı", na=False)
            ].reset_index(drop=True)
            removed = before_len - len(st.session_state.data)
            st.toast(f"🧹 {removed} adet çalışmayan kanal temizlendi!", icon="✅")
            st.rerun()

        if keep_active:
            before_len = len(st.session_state.data)
            st.session_state.data = st.session_state.data[
                st.session_state.data["Durum"].astype(str).str.contains("✅", na=False)
            ].reset_index(drop=True)
            st.toast(f"⭐ Sadece {len(st.session_state.data)} aktif kanal korundu!", icon="⭐")
            st.rerun()

        if toggle_add:
            st.session_state.show_add_channel = not st.session_state.get("show_add_channel", False)
            st.rerun()

        if st.session_state.get("show_add_channel"):
            with st.container():
                st.markdown("##### ➕ Yeni Kanal Ekle")
                with st.form("add_channel_form_inline", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_name = st.text_input("Kanal Adı *")
                        new_grp = st.text_input("Grup *", value="Genel")
                    with c2:
                        new_url = st.text_input("Akış URL *")
                        new_logo = st.text_input("Logo URL")
                    s1, s2 = st.columns([1, 4])
                    with s1:
                        add_submit = st.form_submit_button("Listeye Ekle", type="primary", use_container_width=True)
                    with s2:
                        add_cancel = st.form_submit_button("Kapat")

                    if add_submit:
                        if not new_name.strip() or not new_url.strip():
                            st.error("Kanal Adı ve Akış URL zorunludur!")
                        else:
                            new_t = "HLS" if (".m3u8" in new_url.lower() or "/live/" in new_url.lower()) else "Diğer"
                            new_row = pd.DataFrame([{
                                "Kanal Adı": new_name.strip(),
                                "Grup": new_grp.strip() or "Genel",
                                "URL": new_url.strip(),
                                "LogoURL": new_logo.strip(),
                                "Tür": new_t,
                                "Durum": "❔ Bekliyor",
                            }])
                            st.session_state.data = pd.concat([new_row, st.session_state.data], ignore_index=True)
                            st.session_state.show_add_channel = False
                            st.success(f"✅ '{new_name}' eklendi!")
                            st.rerun()
                    elif add_cancel:
                        st.session_state.show_add_channel = False
                        st.rerun()

        # Data Editor Tablosu
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

        if st.button("💾 Tablodaki Düzenlemeleri Listeye Kaydet", use_container_width=True):
            st.session_state.data = edited_df
            st.toast("✅ Düzenlemeler kaydedildi!", icon="✅")
            time.sleep(0.8)
            st.rerun()

    # =====================================================================
    # SEKME 2: CANLI OYNATICI (SİNEMATİK MOD)
    # =====================================================================
    with tab_player:
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

        p_left, p_right = st.columns([1.3, 2.7])
        with p_left:
            st.markdown("##### 📻 Kanal Seçimi")
            play_name_display = st.selectbox(
                "Oynatılacak Kanal",
                options=["Seçiniz..."] + play_options,
                index=default_index,
                key="player_tab_select_box",
                label_visibility="collapsed",
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
                st.markdown("---")
                if pc.get("logo"):
                    try:
                        st.image(pc["logo"], width=100)
                    except Exception:
                        pass
                st.markdown(f"**Kanal:** {pc['name']}")
                st.markdown(f"**Grup:** {pc.get('group', 'Genel')}")
                
                if "VPN" in pc.get("durum", ""):
                    st.warning("🌍 Bölgesel Kısıtlama (VPN gerekebilir).")
                elif "CORS" in pc.get("durum", ""):
                    st.info("⚠️ CORS Kısıtlı — Yerel proxy aktif.")
                else:
                    st.markdown(f"**Durum:** {pc.get('durum', '❔')}")

                st.caption("📋 Akış URL:")
                st.code(pc["url"], language=None)

                proxy_srv = get_proxy_server()
                st.caption("🛡️ Yerel Proxy URL:")
                st.code(proxy_srv.get_proxy_url(pc["url"]), language=None)

                b_stop, b_dl = st.columns(2)
                with b_stop:
                    if st.button("⏹ Durdur", use_container_width=True):
                        st.session_state.play_channel = None
                        st.rerun()
                with b_dl:
                    single_m3u = f"#EXTM3U\n#EXTINF:-1,{pc['name']}\n{pc['url']}"
                    st.download_button("📥 Bu Kanalı İndir", data=single_m3u, file_name=f"{pc['name']}.m3u", use_container_width=True)
            else:
                st.info("👈 Kanal seçtiğinizde yayın otomatik başlar.")

        with p_right:
            if st.session_state.play_channel:
                pc = st.session_state.play_channel
                st.markdown(f"#### ▶ {pc['name']}")
                components.html(render_live_player(pc["url"], height=420), height=460)
            else:
                st.markdown(
                    "<div style='height:440px;display:flex;flex-direction:column;align-items:center;justify-content:center;background:rgba(11,18,32,0.7);border-radius:14px;border:1px dashed rgba(255,255,255,0.12);'>"
                    "<span style='font-size:3.5rem;'>📺</span>"
                    "<p style='color:#94a3b8;margin-top:12px;font-weight:600;'>Henüz oynatılan kanal yok</p>"
                    "<p style='color:#64748b;font-size:0.85rem;'>Sol menüden bir kanal seçtiğinizde burada canlı izleyebilirsiniz.</p>"
                    "</div>",
                    unsafe_allow_html=True,
                )

    # =====================================================================
    # SEKME 3: DIŞA AKTAR & PAYLAŞ
    # =====================================================================
    with tab_export:
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
        proxy_server.set_m3u_content(m3u_standard, proxied_content=m3u_proxied)

        exp_c1, exp_c2 = st.columns(2)
        with exp_c1:
            st.markdown("#### 📥 Standart Oynatıcı Dosyaları")
            st.caption("VLC, PotPlayer, Kodi, TiviMate gibi standart IPTV oynatıcıları için.")
            sub_m1, sub_m2 = st.columns(2)
            with sub_m1:
                st.download_button(
                    label=f"📥 Standart M3U ({len(df_display)})",
                    data=m3u_standard,
                    file_name="iptv_listesi.m3u",
                    mime="text/plain",
                    type="primary",
                    use_container_width=True,
                )
            with sub_m2:
                st.download_button(
                    label="📥 Genişletilmiş M3U8",
                    data=m3u_standard,
                    file_name="iptv_listesi.m3u8",
                    mime="application/x-mpegURL",
                    use_container_width=True,
                )

            st.markdown("<div style='margin-top:25px;'></div>", unsafe_allow_html=True)
            st.markdown("#### 📊 Veri & Ham Formatlar")
            st.caption("Excel veya programatik analizler için:")
            d1, d2, d3 = st.columns(3)
            with d1:
                st.download_button("📊 Excel / CSV", data=convert_df_to_csv(df_display), file_name="kanallar.csv", mime="text/csv", use_container_width=True)
            with d2:
                st.download_button("📦 JSON", data=convert_df_to_json(df_display), file_name="kanallar.json", mime="application/json", use_container_width=True)
            with d3:
                st.download_button("📄 TXT (Ham URL)", data=convert_df_to_txt(df_display), file_name="linkler.txt", mime="text/plain", use_container_width=True)

        with exp_c2:
            st.markdown("#### 🌍 Smart TV / VPN Köprüsü M3U")
            st.info(
                "💡 **Smart TV İçin Kolay Çözüm:** TV veya mobil cihazınızda VPN kurulu değilse bu seçeneği kullanın! "
                "Akışlar bu bilgisayar üzerinden tünellenir. Bilgisayar açık ve VPN'e bağlı olduğu sürece TV tüm yurt dışı kanalları açar."
            )
            st.download_button(
                label="🌍 VPN Köprüsü M3U İndir",
                data=m3u_proxied,
                file_name="vpn_koprusu_listesi.m3u",
                mime="text/plain",
                type="primary",
                use_container_width=True,
            )
            st.caption("Aynı Wi-Fi/Ağdaki Smart TV'ler için doğrudan Canlı Link:")
            st.code(f"http://{lan_ip}:{proxy_server.port}/proxied_playlist.m3u", language=None)

            st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
            st.markdown("#### 🌐 Canlı Bulut Paylaşımı")
            if st.button("🚀 İnternet Paylaşım Linki Oluştur (termbin.com)", use_container_width=True):
                with st.spinner("Link üretiliyor..."):
                    st.session_state.m3u_cloud_link = network_utils.create_m3u_link(
                        m3u_standard,
                        user_agent=USER_AGENT,
                        disable_ssl_verify=DISABLE_SSL_VERIFY,
                    )
            if st.session_state.get("m3u_cloud_link"):
                st.code(st.session_state.m3u_cloud_link, language=None)

    # =====================================================================
    # SEKME 4: VPN & YURT DIŞI ÇÖZÜMLERİ
    # =====================================================================
    with tab_vpn:
        v_col_settings, v_col_guide = st.columns([1.2, 1.8])
        with v_col_settings:
            st.markdown("#### ⚙️ Proxy & Tünel Ayarları")
            st.caption("Yurt dışı veya bölge engelli akışları aşmak için proxy ve kimlik profili yapılandırması:")

            cfg_proxy = st.text_input(
                "Proxy / VPN Tüneli (HTTP/SOCKS):",
                value=st.session_state.upstream_proxy,
                placeholder="http://127.0.0.1:10808 veya http://proxy:port",
                help="Yerel VPN istemcinizin (Clash, v2ray, xray vb.) veya harici proxy adresiniz.",
                key="tab_vpn_proxy_input",
            )
            profile_list = list(USER_AGENT_PROFILES.keys())
            p_index = profile_list.index(st.session_state.selected_ua_profile) if st.session_state.selected_ua_profile in profile_list else 0
            cfg_profile = st.selectbox(
                "Oynatıcı / Cihaz Profili (User-Agent):",
                profile_list,
                index=p_index,
                help="Sunucuların tarayıcı engellerini aşmak için TiviMate veya VLC seçebilirsiniz.",
                key="tab_vpn_profile_select",
            )
            cfg_ref = st.text_input(
                "Özel Referer Başlığı (Opsiyonel):",
                value=st.session_state.custom_referer,
                placeholder="Örn: https://iptv-provider.com",
                key="tab_vpn_ref_input",
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
                st.success(f"🟢 **Tünel Devrede:** `{st.session_state.upstream_proxy}`\n\nTüm taramalar ve yerel proxy bu tünelden geçiyor.")
            else:
                st.info("⚪ **Doğrudan Bağlantı:** Herhangi bir ara proxy kullanılmıyor.")

        with v_col_guide:
            st.markdown("#### 📘 Yurt Dışı Akışları Çözüm Rehberi")
            st.markdown("""
            * **1. Cihaz Profili Değiştirme:** Yabancı IPTV sunucuları çoğunlukla Google Chrome gibi tarayıcıları 403 Forbidden ile engeller. Soldaki menüden **TiviMate** veya **VLC** seçerek bu engeli anında aşabilirsiniz.
            * **2. Upstream Proxy ile Tünelleme:** Bilgisayarınızda çalışan bir VPN istemciniz (v2ray, xray, sing-box, clash vb.) varsa, adresini (örn: `http://127.0.0.1:10808`) soldaki kutuya girin. Tarayıcı ve yerel proxy tüm istekleri bu tünel üzerinden iletir.
            * **3. Smart TV VPN Köprüsü:** Smart TV'nize VPN kuramıyorsanız, **'📤 Dışa Aktar & Paylaş'** sekmesinden *VPN Köprüsü M3U* dosyasını TV'nize yükleyin. TV akışları bu bilgisayar üzerinden izler.
            * **4. Ücretsiz VPN Seçenekleri:** Hızlı ve ücretsiz tünelleme için bilgisayarınıza **Cloudflare WARP (1.1.1.1)** veya **ProtonVPN Free** kurabilirsiniz.
            """)

else:
    st.markdown(
        f"""
        <div class='empty-state fade-in'>
            <div class='empty-state__icon'>{PAGE_ICON}</div>
            <h2>{PAGE_TITLE}</h2>
            <p>M3U çalma listenizi yükleyin, düzenleyin, sağlık kontrolü yapın veya canlı izleyin.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    card_c1, card_c2 = st.columns(2)
    with card_c1:
        st.markdown("##### 🌐 M3U URL ile Başlat")
        quick_url = st.text_input("M3U Bağlantısı:", placeholder="https://example.com/playlist.m3u", key="quick_c_url")
        quick_tr = st.checkbox("🇹🇷 Sadece TR Kanalları", value=DEFAULT_TR_FILTER, key="quick_c_tr")
        if st.button("🚀 Listeyi İndir ve Aç", use_container_width=True, type="primary", key="quick_c_btn"):
            if quick_url:
                with st.spinner("İndiriliyor..."):
                    try:
                        active_ua = USER_AGENT_PROFILES.get(st.session_state.selected_ua_profile, USER_AGENT)
                        lines = network_utils.fetch_m3u_source(
                            quick_url,
                            user_agent=active_ua,
                            timeout=REQUEST_TIMEOUT,
                            disable_ssl_verify=DISABLE_SSL_VERIFY,
                            proxy_url=st.session_state.upstream_proxy or None,
                        )
                        raw = parse_m3u_lines(lines)
                        filtered = filter_channels(raw, quick_tr)
                        if filtered:
                            st.session_state.data = _ensure_channel_columns(pd.DataFrame(filtered))
                            if quick_url not in st.session_state.recent_urls:
                                st.session_state.recent_urls.insert(0, quick_url)
                            st.rerun()
                        else:
                            st.warning("Kanal bulunamadı.")
                    except Exception as e:
                        st.error(f"Hata: {e}")
            else:
                st.warning("Lütfen bir link girin.")

    with card_c2:
        st.markdown("##### 📂 Dosya Yükleyerek Başlat")
        center_file = st.file_uploader("M3U / M3U8 Dosyası Bırakın", type=["m3u", "m3u8"], key="quick_c_file")
        if center_file:
            source_lines = io.StringIO(center_file.getvalue().decode("utf-8", errors="ignore")).readlines()
            raw = parse_m3u_lines(source_lines)
            filtered = filter_channels(raw, DEFAULT_TR_FILTER)
            if filtered:
                st.session_state.data = _ensure_channel_columns(pd.DataFrame(filtered))
                st.rerun()

# --- Footer ---
st.markdown("---")
st.markdown(
    "<div style='text-align:center;padding:15px;'>"
    "<p style='margin:0;font-size:0.8rem;color:#64748b;'>"
    f"{PAGE_TITLE} v{APP_VERSION} | Streamlit {st.__version__} | Python {sys.version.split()[0]}</p>"
    "</div>",
    unsafe_allow_html=True,
)

