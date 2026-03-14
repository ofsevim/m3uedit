import http.server
import socketserver
import urllib.request
import urllib.parse
import threading
import socket
import logging
import ssl
import re

logger = logging.getLogger(__name__)

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

CHUNK = 64 * 1024


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    _uri_re = re.compile(r'(URI\s*=\s*")([^"]+)(")', re.IGNORECASE)

    def log_message(self, *a):
        pass

    # ═══════════════════════════════════════
    #  ROUTING
    # ═══════════════════════════════════════
    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == "/player":
            self._serve_player(p)
        elif p.path == "/proxy":
            self._serve_proxy(p)
        elif p.path == "/health":
            self._ok(b"ok", "text/plain")
        else:
            self.send_response(404)
            self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    # ═══════════════════════════════════════
    #  /player — Tam HTML Oynatıcı Sayfası
    # ═══════════════════════════════════════
    def _serve_player(self, parsed):
        q = urllib.parse.parse_qs(parsed.query)
        url = q.get("url", [None])[0]
        if not url:
            self.send_response(400)
            self.end_headers()
            return

        host, port = self.server.server_address
        base = f"http://{host}:{port}"
        proxy_url = f"{base}/proxy?url={urllib.parse.quote(url, safe='')}"

        html = self._player_html(url, proxy_url, base)
        self._ok(html.encode("utf-8"), "text/html; charset=utf-8")

    # ═══════════════════════════════════════
    #  /proxy — CORS Proxy (Stream + M3U8)
    # ═══════════════════════════════════════
    def _serve_proxy(self, parsed):
        q = urllib.parse.parse_qs(parsed.query)
        url = q.get("url", [None])[0]
        if not url:
            self.send_response(400)
            self.end_headers()
            return

        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            for h in ("Range", "Accept"):
                v = self.headers.get(h)
                if v:
                    headers[h] = v

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
                ct = resp.getheader("Content-Type", "application/octet-stream")
                status = resp.status
                final_url = resp.url

                is_m3u8 = (
                    "mpegurl" in ct.lower()
                    or url.lower().split("?")[0].endswith(".m3u8")
                    or final_url.lower().split("?")[0].endswith(".m3u8")
                )

                if is_m3u8:
                    content = resp.read()
                    content = self._rewrite_m3u8(content, final_url)
                    self.send_response(status)
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Content-Length", str(len(content)))
                    self._cors()
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_response(status)
                    self.send_header("Content-Type", ct)
                    cl = resp.getheader("Content-Length")
                    if cl:
                        self.send_header("Content-Length", cl)
                    cr = resp.getheader("Content-Range")
                    if cr:
                        self.send_header("Content-Range", cr)
                    ar = resp.getheader("Accept-Ranges")
                    if ar:
                        self.send_header("Accept-Ranges", ar)
                    self._cors()
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    while True:
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        self.wfile.write(chunk)

        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self._cors()
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:
            logger.error(f"Proxy: {e} → {url}")
            try:
                self.send_response(502)
                self._cors()
                self.end_headers()
            except Exception:
                pass

    # ═══════════════════════════════════════
    #  M3U8 Rewriting
    # ═══════════════════════════════════════
    def _proxy_url(self, url):
        h, p = self.server.server_address
        return f"http://{h}:{p}/proxy?url={urllib.parse.quote(url, safe='')}"

    def _abs(self, base, url):
        if url.startswith(("http://", "https://")):
            return url
        resolved = urllib.parse.urljoin(base, url)
        bp = urllib.parse.urlparse(base)
        rp = urllib.parse.urlparse(resolved)
        if bp.query and not rp.query:
            resolved = urllib.parse.urlunparse(rp._replace(query=bp.query))
        return resolved

    def _rewrite_m3u8(self, content, base_url):
        text = content.decode("utf-8", errors="ignore")
        out = []
        for line in text.splitlines():
            s = line.strip()
            if not s:
                out.append(s)
            elif s.startswith("#"):
                def _r(m, b=base_url):
                    u = self._abs(b, m.group(2))
                    return f"{m.group(1)}{self._proxy_url(u)}{m.group(3)}"
                out.append(self._uri_re.sub(_r, s))
            else:
                out.append(self._proxy_url(self._abs(base_url, s)))
        return "\n".join(out).encode("utf-8")

    # ═══════════════════════════════════════
    #  Helpers
    # ═══════════════════════════════════════
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Expose-Headers", "*")

    def _ok(self, data, ct):
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # ═══════════════════════════════════════
    #  Player HTML — Tamamen Bağımsız Sayfa
    # ═══════════════════════════════════════
    def _player_html(self, orig_url, proxy_url, base):
        safe_orig = orig_url.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        safe_proxy = proxy_url.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')

        return f'''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet">
<link href="https://unpkg.com/@videojs/themes@1.0.1/dist/city/index.css" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#000;overflow:hidden;font-family:system-ui,-apple-system,sans-serif}}
.video-js{{width:100vw;height:100vh}}
.vjs-city .vjs-big-play-button{{
    left:50%!important;top:50%!important;transform:translate(-50%,-50%)!important;
    margin:0!important;width:2.5em!important;height:2.5em!important;border-radius:50%!important;
}}
#overlay{{
    position:fixed;inset:0;display:flex;align-items:center;justify-content:center;
    z-index:20;pointer-events:none;color:#fff;text-align:center;
}}
#overlay.lock{{background:rgba(0,0,0,0.7);pointer-events:auto}}
#overlay .card{{
    background:rgba(15,23,42,0.94);padding:24px 34px;border-radius:16px;
    border:1px solid rgba(255,255,255,0.12);backdrop-filter:blur(12px);
    max-width:440px;font-size:0.9rem;line-height:1.5;
}}
.btn{{
    display:inline-block;margin:5px;padding:10px 22px;border:none;border-radius:8px;
    cursor:pointer;font-size:0.82rem;font-weight:600;color:#fff;text-decoration:none;
}}
.btn-blue{{background:#3b82f6}}.btn-green{{background:#10b981}}
.btn-red{{background:#ef4444}}.btn-gray{{background:#475569}}
#dbg{{
    position:fixed;bottom:4px;left:4px;right:4px;font-size:0.58rem;
    color:#94a3b8;max-height:70px;overflow-y:auto;font-family:monospace;
    background:rgba(0,0,0,0.75);padding:5px 8px;border-radius:6px;
    z-index:30;opacity:0;transition:opacity .3s;line-height:1.4;
}}
body:hover #dbg{{opacity:1}}
</style>
</head>
<body>
<video id="vp" class="video-js vjs-theme-city vjs-big-play-centered" controls autoplay playsinline></video>
<div id="overlay"><div class="card"><div id="msg">⏳ Yükleniyor...</div></div></div>
<div id="dbg"></div>

<script src="https://vjs.zencdn.net/8.10.0/video.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.7"></script>

<script>
(function(){{
    var ORIG  = '{safe_orig}';
    var PROXY = '{safe_proxy}';

    var player = videojs('vp', {{
        autoplay:true, controls:true, responsive:true,
        fluid:false, liveui:true, preload:'auto'
    }});

    var ov  = document.getElementById('overlay');
    var msg = document.getElementById('msg');
    var dbg = document.getElementById('dbg');
    var ok  = false;

    function L(m){{ console.log('[P]',m); if(dbg){{dbg.innerHTML+=m+'<br>';dbg.scrollTop=dbg.scrollHeight;}} }}
    function show(m,lock){{ msg.innerHTML=m; ov.style.display='flex'; ov.classList.toggle('lock',!!lock); }}
    function hide(){{ ov.style.display='none'; }}

    var el = player.tech({{IWillNotUseThisInPlugins:true}}).el();

    L('Orig: '+ORIG.substring(0,70));
    L('Proxy: '+PROXY.substring(0,70));

    /* ════ HLS.js ════ */
    if (typeof Hls !== 'undefined' && Hls.isSupported()) {{
        show('🔄 Stream yükleniyor...', false);

        var hls = new Hls({{
            enableWorker: true,
            lowLatencyMode: true,
            manifestLoadingTimeOut: 12000,
            manifestLoadingMaxRetry: 2,
            levelLoadingTimeOut: 10000,
            levelLoadingMaxRetry: 2,
            fragLoadingTimeOut: 15000,
            fragLoadingMaxRetry: 3,
        }});

        /*
         * ✅ KRİTİK: loadSource(PROXY) kullanıyoruz.
         * 
         * Proxy sunucusu M3U8 içindeki TÜM URL'leri
         * http://127.0.0.1:PORT/proxy?url=... şeklinde rewrite etti.
         * 
         * HLS.js bu absolute proxy URL'leri doğrudan kullanıyor.
         * Aynı origin → CORS yok!
         * Proxy → CDN arası server-side → CORS yok!
         */
        hls.loadSource(PROXY);
        hls.attachMedia(el);

        var watchdog = setTimeout(function(){{
            if(!ok) {{
                L('⏱ 20s timeout');
                hls.destroy();
                showFail('Stream 20 saniye içinde yanıt vermedi.');
            }}
        }}, 20000);

        hls.on(Hls.Events.MANIFEST_PARSED, function(e,d){{
            L('📋 Manifest OK — '+d.levels.length+' kalite');
        }});

        hls.on(Hls.Events.FRAG_LOADED, function(){{
            if(!ok){{
                ok = true;
                clearTimeout(watchdog);
                L('✅ İlk segment geldi!');
                hide();
                el.play().catch(function(){{
                    show('▶️ Oynatmak için ekrana tıklayın', false);
                    el.addEventListener('click', function(){{ el.play(); hide(); }}, {{once:true}});
                }});
            }}
        }});

        hls.on(Hls.Events.ERROR, function(e,d){{
            L('⚠ '+d.details+' fatal='+d.fatal);
            if(d.fatal){{
                clearTimeout(watchdog);
                hls.destroy();
                showFail(d.details);
            }}
        }});

    /* ════ Safari Native ════ */
    }} else if (el.canPlayType('application/vnd.apple.mpegURL')) {{
        el.src = PROXY;
        el.addEventListener('playing', function(){{ ok=true; hide(); }}, {{once:true}});
        el.addEventListener('error', function(){{ showFail('Native HLS hatası'); }}, {{once:true}});

    }} else {{
        showFail('Bu tarayıcı HLS desteklemiyor');
    }}

    /* ════ Hata UI ════ */
    function showFail(detail) {{
        L('❌ '+detail);
        show(
            '🚫 Oynatılamadı<br>'+
            '<p style="font-size:0.72rem;color:#94a3b8;margin:6px 0 14px">'+(detail||'Bağlantı hatası')+'</p>'+
            '<button class="btn btn-blue" onclick="location.reload()">🔄 Tekrar</button>'+
            '<button class="btn btn-green" onclick="navigator.clipboard.writeText(\\''+ORIG+'\\');this.textContent=\\'✅ OK!\\'">📋 URL Kopyala</button><br>'+
            '<div style="margin-top:12px;border-top:1px solid rgba(255,255,255,0.1);padding-top:12px">'+
            '<p style="font-size:0.7rem;color:#cbd5e1;margin:0 0 8px">Harici oynatıcıda aç:</p>'+
            '<a href="vlc://'+ORIG+'" class="btn btn-red">▶ VLC</a>'+
            '<a href="potplayer://'+ORIG+'" class="btn btn-gray">▶ PotPlayer</a>'+
            '</div>',
            true
        );
    }}

    el.addEventListener('playing', function(){{ if(!ok){{ok=true;hide();}} }});
}})();
</script>
</body>
</html>'''


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class LocalProxyServer:
    def __init__(self):
        self.port = get_free_port()
        self.server = None
        self.thread = None

    def start(self):
        self.server = ThreadingTCPServer(("127.0.0.1", self.port), ProxyHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"Proxy+Player server on :{self.port}")
        return self.port

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def get_proxy_url(self, url):
        return f"http://127.0.0.1:{self.port}/proxy?url={urllib.parse.quote(url, safe='')}"

    def get_player_url(self, url):
        return f"http://127.0.0.1:{self.port}/player?url={urllib.parse.quote(url, safe='')}"