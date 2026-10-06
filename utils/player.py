"""Safe player HTML, with no automatic third-party stream relays."""

import json

from utils.security import validate_url


def render_live_player(
    stream_url: str, height: int = 420, *, proxy_base_url: str = "", use_proxy: bool = True
) -> str:
    validate_url(stream_url)
    url_json = (
        json.dumps(stream_url, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    proxy_json = json.dumps(proxy_base_url, ensure_ascii=True).replace("<", "\\u003c")
    proxies = (
        '[{name:"Yerel Proxy", fn:function(u){return proxyBase + "&url=" + encodeURIComponent(u);}}]'
        if use_proxy and proxy_base_url
        else '[{name:"Doğrudan", fn:null}]'
    )
    h = str(int(height))

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
    <script src="https://cdn.jsdelivr.net/npm/mpegts.js@1.7.3/dist/mpegts.js"></script>

    <script>
    (function(){{
        var origUrl = {url_json};
        var proxyBase = {proxy_json};
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
        var PROXIES = {proxies};
        // srcdoc inherits its base URI even when the referrer is suppressed.
        var pageUrl = new URL(document.referrer || document.baseURI || window.location.href);
        function isLoopback(host) {{
            return host === 'localhost' || host.endsWith('.localhost')
                || /^127[.]/.test(host) || host === '[::1]';
        }}
        if (PROXIES[0].fn) {{
            var proxyUrl = new URL(proxyBase, pageUrl);
            var remoteLoopback = isLoopback(proxyUrl.hostname) && !isLoopback(pageUrl.hostname);
            var insecureProxy = pageUrl.protocol === 'https:' && proxyUrl.protocol === 'http:';
            if (remoteLoopback || insecureProxy) {{
                PROXIES = [{{name:'Doğrudan', fn:null}}];
            }}
        }}

        function log(m) {{
            console.log('[IPTV]', m);
        }}
        function show(m, lock) {{
            pst.textContent = m;
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
            if (ok) return;
            if (idx >= PROXIES.length) {{
                cleanup();
                showFail();
                return;
            }}

            cleanup();
            var p = PROXIES[idx];
            log('▶ Deneme ' + idx + ': ' + p.name);
            show('🔄 ' + p.name + ' deneniyor...', false);

            var streamUrl = new URL(origUrl);
            var path = streamUrl.pathname.toLowerCase();
            var extension = (streamUrl.searchParams.get('extension') || '').toLowerCase();
            var isTS = path.endsWith('.ts') || extension === 'ts';
            var isMP4 = path.endsWith('.mp4') || path.endsWith('.webm');
            var isDASH = path.endsWith('.mpd');
            var isHLS = !isTS && !isMP4 && !isDASH && (
                path.endsWith('.m3u8') || extension === 'm3u8'
                || path.indexOf('/live/') !== -1 || path.indexOf('/hls') !== -1
                || path.indexOf('playlist') !== -1);

            if (!p.fn && pageUrl.protocol === 'https:' && streamUrl.protocol === 'http:') {{
                showFail('Bu HTTP yayınını HTTPS sayfasında oynatmak için erişilebilir bir HTTPS proxy gerekir. Kanalı indirip VLC ile açabilir veya uygulamayı yerelde çalıştırabilirsiniz.');
                return;
            }}

            /* ── HLS Oynatma ── */
            if (typeof Hls !== 'undefined' && Hls.isSupported() && (isHLS || (!isTS && !isMP4 && !isDASH))) {{
                var cfg = {{
                    enableWorker: true,
                    lowLatencyMode: true,
                    manifestLoadingTimeOut: 8000,
                    fragLoadingTimeOut: 10000,
                    levelLoadingTimeOut: 8000,
                }};

                var hls = new Hls(cfg);
                curHls = hls;

                hls.loadSource(p.fn ? p.fn(origUrl) : origUrl);
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
                    if (!ok) {{ log('İlk segment alındı'); }}
                }});

                hls.on(Hls.Events.ERROR, function(e, d) {{
                    log('⚠ HLS: ' + d.details + ' fatal=' + d.fatal);
                    if (d.fatal) {{
                        clearTimeout(tout);
                        ok = false;
                        tryAttempt(idx + 1);
                    }}
                }});

                return;
            }}

            /* ── MPEG-TS ── */
            if (isTS && typeof mpegts !== 'undefined' && mpegts.isSupported()) {{
                var tsUrl = p.fn ? p.fn(origUrl) : origUrl;

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
            player.src({{src:vUrl, type:isHLS ? 'application/x-mpegURL' : (isDASH ? 'application/dash+xml' : (path.endsWith('.webm') ? 'video/webm' : 'video/mp4'))}});
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
        function showFail(message) {{
            show(message || 'Oynatılamadı. Sağlık kontrolü tarayıcıda oynatmayı doğrulamaz. Doğrudan yayın için sağlayıcının HTTPS/CORS desteği, proxy ile yayın için erişilebilir bir HTTPS proxy gerekir.', true);
            var box = document.getElementById('psb');
            var retry = document.createElement('button');
            retry.className = 'abtn abtn-blue';
            retry.textContent = 'Tekrar dene';
            retry.onclick = function(){{ location.reload(); }};
            box.appendChild(retry);
            var copy = document.createElement('button');
            copy.className = 'abtn abtn-green';
            copy.textContent = 'URL kopyala';
            copy.onclick = function(){{ copyToClipboard(origUrl, copy); }};
            box.appendChild(copy);
        }}

        /* ── Global hata yakalama ── */
        player.on('playing', function(){{ ok=true; hide(); }});
        player.on('error', function(){{ if(!ok) log('Oynatıcı hatası'); }});

        /* ══ BAŞLAT ══ */

        tryAttempt(0);
    }})();
    </script>
    """
