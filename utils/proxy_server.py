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

proxy_ssl_ctx = ssl.create_default_context()
proxy_ssl_ctx.check_hostname = False
proxy_ssl_ctx.verify_mode = ssl.CERT_NONE


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path != "/proxy":
            self.send_response(404)
            self.end_headers()
            return

        query = urllib.parse.parse_qs(parsed_path.query)
        target_url = query.get("url", [None])[0]

        if not target_url:
            self.send_response(400)
            self.end_headers()
            return

        try:
            # ✅ İstemciden gelen bazı header'ları ilet
            headers = {"User-Agent": "Mozilla/5.0"}

            # Referer varsa ilet (bazı CDN'ler kontrol eder)
            client_referer = self.headers.get("Referer")
            if client_referer:
                headers["Referer"] = client_referer

            # Range header'ı ilet (seek işlemi için gerekli)
            client_range = self.headers.get("Range")
            if client_range:
                headers["Range"] = client_range

            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15, context=proxy_ssl_ctx) as response:
                content = response.read()
                content_type = response.getheader("Content-Type", "application/octet-stream")
                status_code = response.status

                # ✅ Redirect sonrası GERÇEK URL'yi al (relative path çözümlemesi için)
                final_url = response.url

                # M3U8 kontrolü
                is_m3u8 = (
                    "mpegurl" in content_type.lower()
                    or target_url.lower().split("?")[0].endswith(".m3u8")
                    or final_url.lower().split("?")[0].endswith(".m3u8")
                )

                if is_m3u8:
                    content = self.rewrite_m3u8(content, final_url)
                    content_type = "application/vnd.apple.mpegurl"

                self.send_response(status_code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Expose-Headers", "*")
                self.send_header("Cache-Control", "no-cache")

                # ✅ Range response header'larını ilet
                content_range = response.getheader("Content-Range")
                if content_range:
                    self.send_header("Content-Range", content_range)
                accept_ranges = response.getheader("Accept-Ranges")
                if accept_ranges:
                    self.send_header("Accept-Ranges", accept_ranges)

                self.end_headers()
                self.wfile.write(content)

        except urllib.error.HTTPError as e:
            logger.error(f"Proxy HTTP error: {e.code} for {target_url}")
            self.send_response(e.code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
        except BrokenPipeError:
            pass  # İstemci bağlantıyı kapattı, normal
        except Exception as e:
            logger.error(f"Proxy fetch error: {e} for {target_url}")
            try:
                self.send_response(502)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(str(e).encode())
            except BrokenPipeError:
                pass

    def _make_proxy_url(self, url):
        """Verilen URL için proxy URL'si oluşturur."""
        host, port = self.server.server_address
        return f"http://{host}:{port}/proxy?url={urllib.parse.quote(url, safe='')}"

    def _resolve_url(self, base_url, url):
        """Relative URL'yi absolute URL'ye çevirir."""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return urllib.parse.urljoin(base_url, url)

    def rewrite_m3u8(self, content, base_url):
        """
        M3U8 içindeki TÜM URL'leri proxy üzerinden yönlendirir.
        - Segment URL'leri (non-# satırlar)
        - #EXT-X-KEY URI="..."
        - #EXT-X-MAP URI="..."  
        - #EXT-X-MEDIA URI="..."
        - #EXT-X-I-FRAME-STREAM-INF URI="..."
        """
        text = content.decode("utf-8", errors="ignore")
        lines = text.splitlines()
        new_lines = []

        # ✅ Regex: #EXT tag'leri içindeki URI="..." değerlerini yakalar
        uri_pattern = re.compile(r'(URI\s*=\s*")([^"]+)(")', re.IGNORECASE)

        for line in lines:
            stripped = line.strip()

            if not stripped:
                new_lines.append(stripped)
                continue

            if stripped.startswith("#"):
                # ✅ #EXT-X-KEY, #EXT-X-MAP, #EXT-X-MEDIA vb. içindeki URI'leri yeniden yaz
                def replace_uri(match):
                    prefix = match.group(1)   # URI="
                    uri = match.group(2)       # actual URL
                    suffix = match.group(3)    # "
                    abs_url = self._resolve_url(base_url, uri)
                    proxy_url = self._make_proxy_url(abs_url)
                    return f"{prefix}{proxy_url}{suffix}"

                new_line = uri_pattern.sub(replace_uri, stripped)
                new_lines.append(new_line)
            else:
                # ✅ Segment URL'si - urljoin ile doğru çözümle
                abs_url = self._resolve_url(base_url, stripped)
                proxy_url = self._make_proxy_url(abs_url)
                new_lines.append(proxy_url)

        return "\n".join(new_lines).encode("utf-8")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_HEAD(self):
        """Bazı player'lar HEAD isteği gönderir."""
        self.do_GET()


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
        logger.info(f"Local CORS Proxy started on port {self.port}")
        return self.port

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Local CORS Proxy stopped")

    def get_proxy_url(self, target_url):
        return f"http://127.0.0.1:{self.port}/proxy?url={urllib.parse.quote(target_url, safe='')}"
