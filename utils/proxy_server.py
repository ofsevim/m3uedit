import http.server
import socketserver
import urllib.request
import urllib.parse
import threading
import socket
import logging
import ssl

logger = logging.getLogger(__name__)

# SSL context for proxy to ignore certificate errors
proxy_ssl_ctx = ssl.create_default_context()
proxy_ssl_ctx.check_hostname = False
proxy_ssl_ctx.verify_mode = ssl.CERT_NONE

class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Multi-threaded HTTP server."""
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
            req = urllib.request.Request(target_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10, context=proxy_ssl_ctx) as response:
                content = response.read()
                content_type = response.getheader("Content-Type", "application/octet-stream")
                
                # Check for M3U8
                if "application/vnd.apple.mpegurl" in content_type.lower() or target_url.lower().split("?")[0].endswith(".m3u8"):
                    content = self.rewrite_m3u8(content, target_url)

                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content)
        except Exception as e:
            logger.error(f"Proxy fetch error: {e} for {target_url}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def rewrite_m3u8(self, content, base_url):
        """Rewrites relative URLs in M3U8 using absolute proxy URLs."""
        lines = content.decode("utf-8", errors="ignore").splitlines()
        new_lines = []
        
        # Determine the base directory
        base_parts = base_url.rsplit("/", 1)
        base_dir = base_parts[0] + "/" if len(base_parts) > 1 else ""
        
        # Get our own host and port
        host, port = self.server.server_address

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                new_lines.append(line)
            else:
                abs_url = line
                if not line.startswith("http"):
                    abs_url = urllib.parse.urljoin(base_dir, line)
                
                # Use ABSOLUTE URL for the proxy to avoid relative path issues in iframes
                proxy_url = f"http://{host}:{port}/proxy?url={urllib.parse.quote(abs_url)}"
                new_lines.append(proxy_url)
        
        return "\n".join(new_lines).encode("utf-8")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

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
        handler = ProxyHandler
        # Using 127.0.0.1 for maximum local compatibility
        self.server = ThreadingTCPServer(("127.0.0.1", self.port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"Local CORS Proxy (Threaded) started on port {self.port}")
        return self.port

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Local CORS Proxy stopped")

    def get_proxy_url(self, target_url):
        return f"http://127.0.0.1:{self.port}/proxy?url={urllib.parse.quote(target_url)}"
