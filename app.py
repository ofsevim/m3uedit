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
        HEALTH_CHECK_MAX_CHANNELS,
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
    HEALTH_CHECK_MAX_CHANNELS = 50

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
        "error": int(statuses.str.contains("❌", na=False).sum()),
        "pending": int(statuses.str.contains("Bekliyor", na=False).sum()),
    }


def _status_style(value: str) -> str:
    status_text = str(value)
    if "✅" in status_text:
        return "color: #7dd3a7; font-weight: 700;"
    if "❌" in status_text:
        return "color: #fda4af; font-weight: 700;"
    if "Bekliyor" in status_text:
        return "color: #fcd34d; font-weight: 700;"
    if "⚠" in status_text or "⏱" in status_text:
        return "color: #fdba74; font-weight: 700;"
    return "color: #cbd5e1; font-weight: 600;"


def render_live_player(stream_url: str, height: int = 420) -> str:
    url = (stream_url or "").replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
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

        /* ── Başarısız UI ── */
        function showFail() {{
            log('❌ Tüm yöntemler başarısız');
            show(
                '🚫 Oynatılamadı<br>' +
                '<p style="font-size:0.75rem;color:#94a3b8;margin:5px 0 12px 0;">' +
                'Bu kanal tarayıcıda CORS/DRM nedeniyle açılamıyor.<br>' +
                'Harici oynatıcı kullanın.</p>' +
                '<button class="abtn abtn-blue" onclick="location.reload()">🔄 Tekrar</button>' +
                '<button class="abtn abtn-green" onclick="navigator.clipboard.writeText(\\'' + origUrl + '\\');this.textContent=\\'✅ Kopyalandı!\\'">📋 URL Kopyala</button><br>' +
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

    url = st.text_input("🌐 M3U Linki Yapıştır:")
    uploaded_file = st.file_uploader("📂 veya M3U Dosyası Yükle", type=["m3u", "m3u8"])
    only_tr = st.checkbox("🇹🇷 Sadece TR Kanalları", value=DEFAULT_TR_FILTER)

    if st.button("🚀 Listeyi Çek ve Tara", use_container_width=True, type="primary"):
        source_lines = None
        start = time.time()
        if url:
            try:
                with st.spinner("Link indiriliyor..."):
                    source_lines = network_utils.fetch_m3u_source(
                        url,
                        user_agent=USER_AGENT,
                        timeout=REQUEST_TIMEOUT,
                        disable_ssl_verify=DISABLE_SSL_VERIFY,
                    )
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
                df = _ensure_channel_columns(pd.DataFrame(filtered))
                st.session_state.data = df
                st.session_state.play_channel = None  # ✅ Yeni liste yüklendiğinde eski oynatmayı sıfırla
                st.success(f"✅ {len(filtered)} kanal bulundu ({elapsed}s)")
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

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("📺 Görünen", len(df_display))
    mc2.metric("📁 Grup", group_count)
    mc3.metric("🟢 Aktif", status_counts["active"])
    mc4.metric("📡 HLS", hls_count)
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

    st.markdown("### İşlemler")

    # --- İşlemler ---
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
                link = network_utils.create_m3u_link(
                    m3u_out,
                    user_agent=USER_AGENT,
                    disable_ssl_verify=DISABLE_SSL_VERIFY,
                )
            if link:
                st.session_state.m3u_link = link
                st.success("Link hazır!")
            else:
                st.error("Link oluşturulamadı.")
    with act3:
        if st.button("🔍 Sağlık Kontrolü", use_container_width=True):
            max_health_channels = HEALTH_CHECK_MAX_CHANNELS if HEALTH_CHECK_MAX_CHANNELS > 0 else len(df_display)
            urls = df_display["URL"].head(max_health_channels).tolist()
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

            results = batch_check_health(
                urls, 
                max_workers=HEALTH_CHECK_MAX_WORKERS,
                timeout=HEALTH_CHECK_TIMEOUT,
                progress_callback=update_progress
            )

            elapsed = round(time.time() - start_time, 1)

            # Sonuçları ana veriye yaz
            for i, u in enumerate(urls):
                st.session_state.data.loc[st.session_state.data["URL"] == u, "Durum"] = results[i]

            # İstatistik göster
            aktif = sum(1 for r in results if "✅" in r)
            oldu = sum(1 for r in results if "❌" in r)
            diger = total - aktif - oldu

            progress_bar.empty()
            status_text.empty()
            st.success(
                f"✅ Tamamlandı ({elapsed}s) — "
                f"🟢 {aktif} aktif | 🔴 {oldu} ölü | 🟡 {diger} belirsiz"
            )
            time.sleep(1.5)
            st.rerun()

    if st.session_state.get("m3u_link"):
        st.markdown("### Paylaşım Linki")
        st.code(st.session_state.m3u_link, language=None)
        st.caption("☝️ Bu linki IPTV oynatıcına yapıştırabilirsin.")

    # --- Canlı Oynatıcı ---
    st.markdown("### 🎬 Canlı Oynatıcı")

    play_options = []      # display name listesi
    play_url_map = {}      # display_name → {name, url, logo, group, durum}

    for idx, row in df_display.iterrows():
        durum = row.get("Durum", "❔").split(" ")[0] if "Durum" in row else "❔"
        base_name = f"{durum} {row['Kanal Adı']}"

        # ✅ Duplicate isim varsa sayaç ekle
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

    # ✅ FIX: Selectbox doğru index ile — rerun sonrası seçim korunuyor
    current_play = st.session_state.get("play_channel")
    default_index = 0  # "Seçiniz..."
    if current_play:
        # Şu an oynayan kanalı bul ve index'ini ayarla
        for i, opt in enumerate(play_options):
            info = play_url_map[opt]
            if info["name"] == current_play.get("name") and info["url"] == current_play.get("url"):
                default_index = i + 1  # +1 çünkü "Seçiniz..." 0. index
                break

    play_name_display = st.selectbox(
        "Oynatılacak Kanal",
        options=["Seçiniz..."] + play_options,
        index=default_index,
        key="play_select_auto"
    )

    # ✅ FIX: Gereksiz rerun kaldırıldı — sadece state güncelleniyor
    if play_name_display != "Seçiniz...":
        selected_info = play_url_map.get(play_name_display)
        if selected_info:
            current = st.session_state.get("play_channel")
            # Sadece farklı bir kanal seçildiyse güncelle
            if not current or current.get("url") != selected_info["url"] or current.get("name") != selected_info["name"]:
                st.session_state.play_channel = selected_info
                st.rerun()
    else:
        # "Seçiniz..." seçildi ve oynatılan kanal varsa durdur
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
            if "CORS" in pc.get("durum", ""):
                st.warning("⚠️ CORS Kısıtlı — Proxy aktif.")
        with pcol2:
            st.markdown(f"### ▶ {pc['name']}")
            components.html(
                render_live_player(pc["url"], height=380),
                height=420,
            )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⏹ Durdur", use_container_width=True):
                st.session_state.play_channel = None
                st.rerun()
        with col2:
            single_m3u = f"#EXTM3U\n#EXTINF:-1,{pc['name']}\n{pc['url']}"
            st.download_button(
                "📥 Harici Oynatıcı (M3U)",
                data=single_m3u,
                file_name=f"{pc['name']}.m3u",
                type="secondary",
                use_container_width=True,
                help="VLC veya PotPlayer ile açmak için indirin.",
            )
        st.markdown("---")

    # --- Kanal Tablosu ---
    st.markdown("### Kanal Tablosu")
    display_cols = [c for c in ["Durum", "Grup", "Kanal Adı", "URL", "Tür"] if c in df_display.columns]
    table_df = df_display[display_cols] if display_cols else df_display
    styled_df = table_df.style
    if "Durum" in table_df.columns:
        styled_df = styled_df.map(_status_style, subset=["Durum"])
    if "Kanal Adı" in table_df.columns:
        styled_df = styled_df.set_properties(subset=["Kanal Adı"], **{"font-weight": "700", "color": "#f8fafc"})
    if "Grup" in table_df.columns:
        styled_df = styled_df.set_properties(subset=["Grup"], **{"color": "#cbd5e1"})

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=TABLE_HEIGHT,
        column_config={
            "URL": st.column_config.TextColumn("URL", width="large"),
            "Tür": st.column_config.TextColumn("Tür", width="small"),
            "Durum": st.column_config.TextColumn("Durum", width="small"),
        },
    )

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
