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

# Config'den tarayıcı User-Agent'ını çek, hata durumunda güvenli bir varsayılan kullan
try:
    from utils.config import USER_AGENT
except ImportError:
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

proxy_ssl_ctx = ssl.create_default_context()
proxy_ssl_ctx.check_hostname = False
proxy_ssl_ctx.verify_mode = ssl.CERT_NONE

CHUNK_SIZE = 64 * 1024


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self._handle_request(send_body=True)

    def do_HEAD(self):
        self._handle_request(send_body=False)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def _handle_request(self, send_body=True):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # ── 🆕 YEREL ROTA: /playlist.m3u veya /playlist ──
        # Bu rota, kullanıcının oluşturduğu M3U çalma listesini yerel proxy üzerinden sunar.
        # Bellek sızıntılarını önlemek için bu veriyi diskteki geçici bir dosyadan stream ederiz.
        if parsed_path.path in ("/playlist.m3u", "/playlist"):
            import os
            proxy_instance = getattr(self.server, "proxy_instance", None)
            file_path = getattr(proxy_instance, "playlist_file", None) if proxy_instance else None
            
            if not file_path or not os.path.exists(file_path):
                self.send_response(404)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                if send_body:
                    self.wfile.write("Henüz bir çalma listesi oluşturulmadı.".encode("utf-8"))
                return

            try:
                file_size = os.path.getsize(file_path)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-mpegurl; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="playlist.m3u"')
                self.send_header("Content-Length", str(file_size))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                
                if send_body:
                    with open(file_path, "rb") as f:
                        while True:
                            chunk = f.read(64 * 1024)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
            except OSError as e:
                logger.error(f"Error serving playlist file: {e}")
                self.send_response(500)
                self.end_headers()
            return

        if parsed_path.path != "/proxy":
            self.send_response(404)
            self.end_headers()
            return

        query = urllib.parse.parse_qs(parsed_path.query)
        target_url = query.get("url", [None])[0]
        
        # 🛡️ GÜVENLİK FİXİ: SSRF ve LFI (Local File Inclusion) önleme
        # Sadece http ve https protokollerine izin ver (örn. file:// engellenir)
        if not target_url or not target_url.startswith(("http://", "https://")):
            self.send_response(400)
            self.end_headers()
            return

        try:
            # 🌐 İYİLEŞTİRME: Config'den gelen tarayıcı User-Agent'ını kullan
            headers = {"User-Agent": USER_AGENT}
            for h in ("Referer", "Range", "Accept"):
                val = self.headers.get(h)
                if val:
                    headers[h] = val

            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15, context=proxy_ssl_ctx) as resp:
                content_type = resp.getheader("Content-Type", "application/octet-stream")
                status_code = resp.status
                final_url = resp.url

                is_m3u8 = (
                    "mpegurl" in content_type.lower()
                    or target_url.lower().split("?")[0].endswith(".m3u8")
                    or final_url.lower().split("?")[0].endswith(".m3u8")
                )

                # ── CORS header'ları ──
                cors_headers = {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Expose-Headers": "*",
                    "Cache-Control": "no-cache",
                }

                if is_m3u8:
                    # M3U8 → tamamen oku, yeniden yaz
                    content = resp.read()
                    content = self.rewrite_m3u8(content, final_url)
                    content_type = "application/vnd.apple.mpegurl"

                    self.send_response(status_code)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(content)))
                    for k, v in cors_headers.items():
                        self.send_header(k, v)
                    self.end_headers()
                    if send_body:
                        self.wfile.write(content)
                else:
                    # Binary/TS → stream et
                    self.send_response(status_code)
                    self.send_header("Content-Type", content_type)

                    cl = resp.getheader("Content-Length")
                    if cl:
                        self.send_header("Content-Length", cl)
                    cr = resp.getheader("Content-Range")
                    if cr:
                        self.send_header("Content-Range", cr)
                    ar = resp.getheader("Accept-Ranges")
                    if ar:
                        self.send_header("Accept-Ranges", ar)

                    for k, v in cors_headers.items():
                        self.send_header(k, v)
                    self.end_headers()

                    if send_body:
                        while True:
                            chunk = resp.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            self.wfile.write(chunk)

        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:
            logger.error(f"Proxy error: {e} for {target_url}")
            try:
                self.send_response(502)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError):
                pass

    # ── M3U8 Rewriting ──

    _uri_re = re.compile(r'(URI\s*=\s*")([^"]+)(")', re.IGNORECASE)

    def _make_proxy_url(self, url):
        host, port = self.server.server_address
        return f"http://{host}:{port}/proxy?url={urllib.parse.quote(url, safe='')}"

    def _resolve_url(self, base_url, url):
        if url.startswith(("http://", "https://")):
            return url
        resolved = urllib.parse.urljoin(base_url, url)
        # Token propagation
        bp = urllib.parse.urlparse(base_url)
        rp = urllib.parse.urlparse(resolved)
        if bp.query and not rp.query:
            resolved = urllib.parse.urlunparse(rp._replace(query=bp.query))
        return resolved

    def rewrite_m3u8(self, content, base_url):
        text = content.decode("utf-8", errors="ignore")
        new_lines = []

        for line in text.splitlines():
            s = line.strip()
            if not s:
                new_lines.append(s)
            elif s.startswith("#"):
                def _repl(m, _base=base_url):
                    u = self._resolve_url(_base, m.group(2))
                    return f"{m.group(1)}{self._make_proxy_url(u)}{m.group(3)}"
                new_lines.append(self._uri_re.sub(_repl, s))
            else:
                abs_url = self._resolve_url(base_url, s)
                new_lines.append(self._make_proxy_url(abs_url))

        return "\n".join(new_lines).encode("utf-8")


class LocalProxyServer:
    def __init__(self):
        self.server = None
        self.thread = None
        self.port = None
        
        # Streamlit Cloud'da RAM şişmesini önlemek için çalma listesini diskteki geçici bir dosyada saklarız.
        # Bu sayede devasa çalma listeleri Python heap belleğinde tutulmaz.
        import os
        from utils.visitor_counter import VisitorCounter
        self.playlist_file = VisitorCounter._resolve_path("temp_playlist.m3u")

    def start(self):
        # 🔄 AĞDAKİ DİĞER CİHAZLARIN ERİŞEBİLMESİ İÇİN:
        # Sunucuyu "0.0.0.0" adresine bağlayarak, aynı Wi-Fi/Ağdaki Smart TV veya 
        # telefonların da bu çalma listesine ve proxy'ye erişebilmesini sağlıyoruz.
        self.server = ThreadingTCPServer(("0.0.0.0", 0), ProxyHandler)
        self.server.proxy_instance = self
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"CORS Proxy on :{self.port}")
        return self.port

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            # Geçici dosyayı temizle
            import os
            try:
                if os.path.exists(self.playlist_file):
                    os.remove(self.playlist_file)
            except OSError:
                pass

    def get_proxy_url(self, target_url):
        return f"http://127.0.0.1:{self.port}/proxy?url={urllib.parse.quote(target_url, safe='')}"

    def set_m3u_content(self, content: str):
        """Çalma listesi içeriğini RAM yerine geçici bir dosyaya yazar."""
        try:
            with open(self.playlist_file, "w", encoding="utf-8", newline="") as f:
                f.write(content)
        except OSError as e:
            logger.error(f"Failed to write playlist to file: {e}")