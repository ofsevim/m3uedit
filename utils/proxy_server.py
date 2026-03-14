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


def _get_local_ip():
    """Makinenin gerçek LAN IP'sini bul."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    _uri_re = re.compile(r'(URI\s*=\s*")([^"]+)(")', re.IGNORECASE)

    def log_message(self, *a):
        pass

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == "/player":
            self._serve_player(p)
        elif p.path == "/proxy":
            self._serve_proxy(p)
        elif p.path == "/health":
            self._simple_response(200, b"ok", "text/plain")
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

    # ══════════ /player ══════════
    def _serve_player(self, parsed):
        q = urllib.parse.parse_qs(parsed.query)
        url = q.get("url", [None])[0]
        if not url:
            self.send_response(400)
            self.end_headers()
            return

        base = self._base_url()
        proxy_url = f"{base}/proxy?url={urllib.parse.quote(url, safe='')}"
        html = self._player_html(url, proxy_url)
        self._simple_response(200, html.encode("utf-8"), "text/html; charset=utf-8")

    # ══════════ /proxy ══════════
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
                    for hdr in ("Content-Length", "Content-Range", "Accept-Ranges"):
                        v = resp.getheader(hdr)
                        if v:
                            self.send_header(hdr, v)
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

    # ══════════ M3U8 Rewrite ══════════
    def _base_url(self):
        # ✅ Her zaman erişilebilir adresi kullan
        return f"http://{self.server.accessible_host}:{self.server.server_address[1]}"

    def _proxy_url_for(self, url):
        return f"{self._base_url()}/proxy?url={urllib.parse.quote(url, safe='')}"

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
                    return f"{m.group(1)}{self._proxy_url_for(u)}{m.group(3)}"
                out.append(self._uri_re.sub(_r, s))
            else:
                out.append(self._proxy_url_for(self._abs(base_url, s)))
        return "\n".join(out).encode("utf-8")

    # ══════════ Helpers ══════════
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Expose-Headers", "*")

    def _simple_response(self, code, data, ct):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    # ══════════ Player HTML ══════════
    def _player_html(self, orig_url, proxy_url):
        so = orig_url.replace("\\","\\\\").replace("'","\\'").replace('"','\\"')
        sp = proxy_url.replace("\\","\\\\").replace("'","\\'").replace('"','\\"')

        return f'''<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet">
<link href="https://unpkg.com/@videojs/themes@1.0.1/dist/city/index.css" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#000;overflow:hidden}}
.video-js{{width:100vw;height:100vh}}
.vjs-city .vjs-big-play-button{{left:50%!important;top:50%!important;transform:translate(-50%,-50%)!important;margin:0!important;width:2.5em!important;height:2.5em!important;border-radius:50%!important}}
#ov{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;z-index:20;pointer-events:none;color:#fff;text-align:center;font-family:system-ui}}
#ov.lock{{background:rgba(0,0,0,.7);pointer-events:auto}}
#ov .cd{{background:rgba(15,23,42,.94);padding:24px 34px;border-radius:16px;border:1px solid rgba(255,255,255,.12);backdrop-filter:blur(12px);max-width:440px;font-size:.9rem}}
.b{{display:inline-block;margin:5px;padding:10px 22px;border:none;border-radius:8px;cursor:pointer;font-size:.82rem;font-weight:600;color:#fff;text-decoration:none}}
.b1{{background:#3b82f6}}.b2{{background:#10b981}}.b3{{background:#ef4444}}.b4{{background:#475569}}
#dg{{position:fixed;bottom:4px;left:4px;right:4px;font-size:.58rem;color:#94a3b8;max-height:70px;overflow-y:auto;font-family:monospace;background:rgba(0,0,0,.75);padding:5px 8px;border-radius:6px;z-index:30;opacity:0;transition:opacity .3s;line-height:1.4}}
body:hover #dg{{opacity:1}}
</style></head><body>
<video id="vp" class="video-js vjs-theme-city vjs-big-play-centered" controls autoplay playsinline></video>
<div id="ov"><div class="cd"><div id="ms">⏳ Yükleniyor...</div></div></div>
<div id="dg"></div>
<script src="https://vjs.zencdn.net/8.10.0/video.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.7"></script>
<script>
(function(){{
var O='{so}',P='{sp}';
var pl=videojs('vp',{{autoplay:true,controls:true,responsive:true,fluid:false,liveui:true,preload:'auto'}});
var ov=document.getElementById('ov'),ms=document.getElementById('ms'),dg=document.getElementById('dg');
var ok=false;
function L(m){{console.log('[P]',m);if(dg){{dg.innerHTML+=m+'<br>';dg.scrollTop=dg.scrollHeight}}}}
function S(m,l){{ms.innerHTML=m;ov.style.display='flex';ov.classList.toggle('lock',!!l)}}
function H(){{ov.style.display='none'}}
var el=pl.tech({{IWillNotUseThisInPlugins:true}}).el();
L('Proxy: '+P.substring(0,80));
if(typeof Hls!=='undefined'&&Hls.isSupported()){{
    S('🔄 Yükleniyor...',false);
    var h=new Hls({{enableWorker:true,lowLatencyMode:true,manifestLoadingTimeOut:12000,manifestLoadingMaxRetry:2,levelLoadingTimeOut:10000,fragLoadingTimeOut:15000,fragLoadingMaxRetry:3}});
    h.loadSource(P);
    h.attachMedia(el);
    var wd=setTimeout(function(){{if(!ok){{L('⏱ Timeout');h.destroy();F('Timeout')}}}},20000);
    h.on(Hls.Events.MANIFEST_PARSED,function(e,d){{L('📋 Manifest: '+d.levels.length+' level')}});
    h.on(Hls.Events.FRAG_LOADED,function(){{if(!ok){{ok=true;clearTimeout(wd);L('✅ Segment OK');H();el.play().catch(function(){{S('▶️ Tıklayın',false);el.addEventListener('click',function(){{el.play();H()}},{{once:true}})}});}}}});
    h.on(Hls.Events.ERROR,function(e,d){{L('⚠ '+d.details+' fatal='+d.fatal);if(d.fatal){{clearTimeout(wd);h.destroy();F(d.details)}}}});
}}else if(el.canPlayType('application/vnd.apple.mpegURL')){{
    el.src=P;el.addEventListener('playing',function(){{ok=true;H()}},{{once:true}});
    el.addEventListener('error',function(){{F('Native HLS error')}},{{once:true}});
}}else{{F('HLS not supported')}}
function F(d){{
    L('❌ '+d);
    S('🚫 Oynatılamadı<br><p style="font-size:.72rem;color:#94a3b8;margin:6px 0 14px">'+(d||'Hata')+'</p>'+
    '<button class="b b1" onclick="location.reload()">🔄 Tekrar</button>'+
    '<button class="b b2" onclick="navigator.clipboard.writeText(\\''+O+'\\');this.textContent=\\'✅!\\'">📋 Kopyala</button><br>'+
    '<div style="margin-top:12px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px">'+
    '<a href="vlc://'+O+'" class="b b3">▶ VLC</a>'+
    '<a href="potplayer://'+O+'" class="b b4">▶ PotPlayer</a></div>',true);
}}
el.addEventListener('playing',function(){{if(!ok){{ok=true;H()}}}});
}})();
</script></body></html>'''


class LocalProxyServer:
    def __init__(self):
        self.port = get_free_port()
        self.server = None
        self.thread = None
        self.host = "0.0.0.0"

        # ✅ Tarayıcıdan erişilebilir IP
        self.accessible_host = _get_local_ip()

    def start(self):
        # ✅ 0.0.0.0'da dinle — tüm interface'lerden erişilebilir
        self.server = ThreadingTCPServer((self.host, self.port), ProxyHandler)
        self.server.accessible_host = self.accessible_host
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"Proxy+Player on {self.accessible_host}:{self.port}")
        return self.port

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def get_proxy_url(self, url):
        return f"http://{self.accessible_host}:{self.port}/proxy?url={urllib.parse.quote(url, safe='')}"

    def get_player_url(self, url):
        return f"http://{self.accessible_host}:{self.port}/player?url={urllib.parse.quote(url, safe='')}"