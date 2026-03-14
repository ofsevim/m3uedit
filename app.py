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
    ctx = _create_ssl_context()

    # 1) paste.rs
    try:
        req = urllib.request.Request(
            "https://paste.rs/",
            data=m3u_content.encode("utf-8"),
            headers={"User-Agent": USER_AGENT, "Content-Type": "text/plain"},
        )
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
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
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            paste_url = resp.read().decode("utf-8").strip().strip('"')
            if not paste_url.endswith(".txt"):
                paste_url = paste_url.rstrip("/") + ".txt"
            return paste_url
    except Exception as e:
        logger.error(f"M3U link oluşturma hatası: {e}", exc_info=True)
        return ""


def render_live_player(stream_url: str, height: int = 420) -> str:
    url = (stream_url or "").replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
    h = str(height)

    proxy_server = get_proxy_server()
    local_proxy_base = f"http://127.0.0.1:{proxy_server.port}/proxy?url="

    return f"""
    <link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet" />
    <link href="https://unpkg.com/@videojs/themes@1.0.1/dist/city/index.css" rel="stylesheet">
    <style>
        .pw {{
            position:relative; width:100%; height:{h}px; background:#000;
            border-radius:12px; overflow:hidden; border:1px solid rgba(255,255,255,0.08);
        }}
        .video-js {{ width:100%; height:100%; }}
        .vjs-city .vjs-big-play-button {{
            left:50%!important; top:50%!important; transform:translate(-50%,-50%)!important;
            margin:0!important; width:2.5em!important; height:2.5em!important; border-radius:50%!important;
        }}
        #ps {{
            position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
            z-index:20; pointer-events:none; text-align:center; color:#fff;
        }}
        #ps.active {{ background:rgba(0,0,0,0.65); pointer-events:auto; }}
        #ps .box {{
            background:rgba(15,23,42,0.92); padding:22px 32px; border-radius:16px;
            font-size:0.92rem; border:1px solid rgba(255,255,255,0.15); backdrop-filter:blur(10px);
            max-width:440px;
        }}
        .ab {{
            display:inline-block; margin:5px; padding:10px 20px; border:none; border-radius:8px;
            cursor:pointer; font-size:0.82rem; font-weight:600; color:#fff; text-decoration:none;
        }}
        .ab-b {{ background:#3b82f6; }} .ab-g {{ background:#10b981; }}
        .ab-r {{ background:#ef4444; }} .ab-d {{ background:#475569; }}
        #dl {{
            position:absolute; bottom:4px; left:4px; right:4px; font-size:0.6rem;
            color:#94a3b8; max-height:70px; overflow-y:auto; font-family:monospace;
            background:rgba(0,0,0,0.7); padding:5px 8px; border-radius:6px;
            display:none; z-index:30; line-height:1.4;
        }}
        .pw:hover #dl {{ display:block; }}
    </style>

    <div class="pw">
        <video id="vp" class="video-js vjs-theme-city vjs-big-play-centered"></video>
        <div id="ps"><div class="box"><div id="pst">⏳ Başlatılıyor...</div></div></div>
        <div id="dl"></div>
    </div>

    <script src="https://vjs.zencdn.net/8.10.0/video.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.7"></script>
    <script src="https://cdn.jsdelivr.net/npm/mpegts.js@latest/dist/mpegts.js"></script>

    <script>
    (function(){{
        var SRC = '{url}';
        if (!SRC) return;

        var player = videojs('vp', {{
            autoplay:true, controls:true, responsive:true, fluid:false,
            liveui:true, preload:'auto'
        }});

        var ps  = document.getElementById('ps');
        var pst = document.getElementById('pst');
        var dl  = document.getElementById('dl');
        var done = false;        // Başarılı mı?
        var curHls = null;
        var curTs  = null;
        var curTout = null;      // Aktif timeout

        /* ── Proxy Tanımları ── */
        var LOCAL_PROXY = '{local_proxy_base}';
        var STRATEGIES = [
            {{
                name: 'Doğrudan',
                proxy: null
            }},
            {{
                name: 'Yerel Proxy',
                proxy: function(u) {{ return LOCAL_PROXY + encodeURIComponent(u); }}
            }},
            {{
                name: 'AllOrigins',
                proxy: function(u) {{ return 'https://api.allorigins.win/raw?url=' + encodeURIComponent(u); }}
            }},
            {{
                name: 'CorsProxy',
                proxy: function(u) {{ return 'https://corsproxy.io/?' + encodeURIComponent(u); }}
            }}
        ];

        function L(m) {{
            console.log('[P]', m);
            if (dl) {{ dl.innerHTML += m + '<br>'; dl.scrollTop = dl.scrollHeight; }}
        }}
        function show(m, lock) {{
            pst.innerHTML = m;
            ps.style.display = 'flex';
            ps.classList.toggle('active', !!lock);
        }}
        function hide() {{ ps.style.display = 'none'; }}

        function clearTout() {{
            if (curTout) {{ clearTimeout(curTout); curTout = null; }}
        }}

        function cleanup() {{
            clearTout();
            if (curHls) {{ try {{ curHls.destroy(); }} catch(e){{}} curHls = null; }}
            if (curTs)  {{ try {{ curTs.unload(); curTs.detachMediaElement(); curTs.destroy(); }} catch(e){{}} curTs = null; }}
        }}

        function success(label) {{
            if (done) return;
            done = true;
            clearTout();
            L('✅ BAŞARILI: ' + label);
            hide();
        }}

        var mediaEl = player.tech({{IWillNotUseThisInPlugins:true}}).el();

        /* ══════════════════════════════════════════════
           DENEME FONKSİYONU
           ══════════════════════════════════════════════ */
        function attempt(idx) {{
            if (done || idx >= STRATEGIES.length) {{
                if (!done) showFail();
                return;
            }}

            cleanup();
            var S = STRATEGIES[idx];
            var proxyFn = S.proxy;
            L('━━━ Deneme ' + idx + ': ' + S.name + ' ━━━');
            show('🔄 ' + S.name + ' deneniyor...', false);

            var lower = SRC.toLowerCase();
            var isHLS = /\\.m3u8|m3u8|\/live\/|\/hls|playlist/.test(lower);
            var isTS  = lower.endsWith('.ts') && !isHLS;

            /* ────────── HLS ────────── */
            if (typeof Hls !== 'undefined' && Hls.isSupported() && (isHLS || !isTS)) {{

                var errorCount = 0;         // ✅ Non-fatal hata sayacı
                var manifestOk = false;     // ✅ Manifest yüklendi mi?
                var firstFragOk = false;    // ✅ İlk fragment yüklendi mi?

                var cfg = {{
                    enableWorker: true,
                    lowLatencyMode: true,

                    /* ✅ Timeout'ları kısalt — ölü proxy'de az bekle */
                    manifestLoadingTimeOut: 6000,
                    manifestLoadingMaxRetry: 0,         // Manifest başarısız → hemen sonraki deneme
                    levelLoadingTimeOut: 6000,
                    levelLoadingMaxRetry: 0,
                    fragLoadingTimeOut: 8000,
                    fragLoadingMaxRetry: 1,             // ✅ 1 retry sonra fatal yap
                    fragLoadingMaxRetryTimeout: 3000,
                }};

                /* ✅ Proxy varsa xhrSetup ile araya gir */
                if (proxyFn) {{
                    cfg.xhrSetup = function(xhr, reqUrl) {{
                        var proxied = proxyFn(reqUrl);
                        L('  → ' + reqUrl.substring(0, 55) + '...');
                        xhr.open('GET', proxied, true);
                    }};
                }}

                var hls = new Hls(cfg);
                curHls = hls;
                hls.loadSource(SRC);    // ✅ HER ZAMAN orijinal URL
                hls.attachMedia(mediaEl);

                /* ✅ Genel güvenlik timeout'u — 15s içinde fragment gelmezse sonraki */
                curTout = setTimeout(function() {{
                    if (!done && !firstFragOk) {{
                        L('⏱ Genel timeout (' + S.name + ')');
                        attempt(idx + 1);
                    }}
                }}, 15000);

                hls.on(Hls.Events.MANIFEST_PARSED, function(e, d) {{
                    manifestOk = true;
                    L('📋 Manifest OK (' + d.levels.length + ' kalite)');
                    /* Manifest yüklendi ama segment'ler CORS'a takılabilir
                       → henüz success deme, ilk fragment'i bekle! */
                }});

                /* ✅ KRİTİK: İlk fragment GERÇEKTEN yüklendiğinde success */
                hls.on(Hls.Events.FRAG_LOADED, function() {{
                    if (!firstFragOk) {{
                        firstFragOk = true;
                        L('📦 İlk segment yüklendi!');
                        success(S.name);
                        mediaEl.play().catch(function(err) {{
                            L('Autoplay engellendi');
                            show('▶️ Tıklayın', false);
                            mediaEl.addEventListener('click', function() {{
                                mediaEl.play(); hide();
                            }}, {{once:true}});
                        }});
                    }}
                }});

                hls.on(Hls.Events.ERROR, function(e, d) {{
                    L('⚠ ' + d.details + ' fatal=' + d.fatal);

                    if (d.fatal) {{
                        /* Fatal hata → hemen sonraki deneme */
                        attempt(idx + 1);
                        return;
                    }}

                    /* ✅ Non-fatal hataları say — 3 olursa terk et */
                    errorCount++;
                    L('  (non-fatal #' + errorCount + ')');

                    if (errorCount >= 3 && !firstFragOk) {{
                        L('🚫 Çok fazla hata, sonraki denemeye geçiliyor');
                        attempt(idx + 1);
                    }}
                }});

                return;
            }}

            /* ────────── Safari Native HLS ────────── */
            if (isHLS && mediaEl.canPlayType('application/vnd.apple.mpegURL')) {{
                var playUrl = proxyFn ? proxyFn(SRC) : SRC;
                L('Safari HLS: ' + playUrl.substring(0,60));
                mediaEl.src = playUrl;
                curTout = setTimeout(function(){{ if(!done) attempt(idx+1); }}, 10000);
                mediaEl.addEventListener('playing', function(){{
                    success(S.name);
                }}, {{once:true}});
                mediaEl.addEventListener('error', function(){{
                    clearTout(); attempt(idx+1);
                }}, {{once:true}});
                return;
            }}

            /* ────────── MPEG-TS ────────── */
            if (isTS && typeof mpegts !== 'undefined' && mpegts.isSupported()) {{
                var tsUrl = proxyFn ? proxyFn(SRC) : SRC;
                L('TS: ' + tsUrl.substring(0,60));
                var m = mpegts.createPlayer({{type:'mpegts', url:tsUrl, isLive:true}});
                curTs = m;
                m.attachMediaElement(mediaEl);
                m.load(); m.play();
                curTout = setTimeout(function(){{ if(!done) attempt(idx+1); }}, 10000);
                m.on(mpegts.Events.ERROR, function(){{ clearTout(); attempt(idx+1); }});
                mediaEl.addEventListener('playing', function(){{ success(S.name); }}, {{once:true}});
                return;
            }}

            /* ────────── Direct Video ────────── */
            var vUrl = proxyFn ? proxyFn(SRC) : SRC;
            player.src({{src:vUrl, type:'video/mp4'}});
            curTout = setTimeout(function(){{ if(!done) attempt(idx+1); }}, 8000);
            player.one('playing', function(){{ success(S.name); }});
            player.one('error', function(){{ clearTout(); attempt(idx+1); }});
            player.play().catch(function(){{}});
        }}

        /* ── Başarısız UI ── */
        function showFail() {{
            L('❌ Tüm yöntemler başarısız');
            show(
                '🚫 Bu kanal tarayıcıda oynatılamıyor<br>' +
                '<p style="font-size:0.72rem;color:#94a3b8;margin:6px 0 14px 0;">' +
                'CORS/DRM kısıtlaması nedeniyle tarayıcı engelledi.<br>' +
                'Aşağıdaki yöntemlerle izleyebilirsiniz:</p>' +

                '<button class="ab ab-b" onclick="location.reload()">🔄 Tekrar</button>' +
                '<button class="ab ab-g" onclick="navigator.clipboard.writeText(\\'' + SRC + '\\');this.textContent=\\'✅ OK!\\'">📋 URL Kopyala</button><br>' +

                '<div style="margin-top:12px;border-top:1px solid rgba(255,255,255,0.1);padding-top:12px;">' +
                '<p style="font-size:0.7rem;color:#cbd5e1;margin:0 0 8px 0;">Harici oynatıcıda aç:</p>' +
                '<a href="vlc://' + SRC + '" class="ab ab-r">▶ VLC</a>' +
                '<a href="potplayer://' + SRC + '" class="ab ab-d">▶ PotPlayer</a>' +
                '</div>',
                true
            );
        }}

        /* ── Global playing event ── */
        mediaEl.addEventListener('playing', function() {{
            if (!done) success('media playing');
        }});

        /* ══ BAŞLAT ══ */
        L('URL: ' + SRC);
        attempt(0);
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
                st.session_state.play_channel = None  # ✅ Yeni liste yüklendiğinde eski oynatmayı sıfırla
                st.success(f"✅ {len(filtered)} kanal bulundu ({elapsed}s)")
            else:
                st.warning("⚠️ Kanal bulunamadı.")

    st.markdown("---")

    # Filtreler
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
                link = create_m3u_link(m3u_out)
            if link:
                st.session_state.m3u_link = link
                st.success("Link hazır!")
            else:
                st.error("Link oluşturulamadı.")
    with act3:
        if st.button("🔍 Sağlık Kontrolü", use_container_width=True):
            urls = df_display["URL"].tolist()
            total = len(urls)

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
                max_workers=50, 
                timeout=3.0, 
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
        st.code(st.session_state.m3u_link, language=None)
        st.caption("☝️ Bu linki IPTV oynatıcına yapıştırabilirsin.")

    # --- Canlı Oynatıcı ---
    st.markdown("### 🎬 Canlı Oynatıcı")

    # ✅ FIX: Unique display names (index ekleyerek duplicate önleme)
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
    display_cols = [c for c in ["Durum", "Grup", "Kanal Adı", "URL", "Tür"] if c in df_display.columns]
    st.dataframe(
        df_display[display_cols] if display_cols else df_display,
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