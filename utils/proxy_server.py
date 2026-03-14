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
            headers = {"User-Agent": "Mozilla/5.0"}
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
        logger.info(f"CORS Proxy on :{self.port}")
        return self.port

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def get_proxy_url(self, target_url):
        return f"http://127.0.0.1:{self.port}/proxy?url={urllib.parse.quote(target_url, safe='')}"