import http.server
import socketserver
import urllib.request
import urllib.parse
import threading
import socket
import logging
import re

logger = logging.getLogger(__name__)

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy logs
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
            self.wfile.write(b"Missing url parameter")
            return

        try:
            req = urllib.request.Request(target_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read()
                content_type = response.getheader("Content-Type", "application/octet-stream")
                
                # Check if it's an M3U8 playlist that needs rewriting
                if "application/vnd.apple.mpegurl" in content_type.lower() or target_url.lower().endswith(".m3u8"):
                    content = self.rewrite_m3u8(content, target_url)

                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.end_headers()
                self.wfile.write(content)
        except Exception as e:
            logger.error(f"Proxy error for {target_url}: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def rewrite_m3u8(self, content, base_url):
        """Rewrites relative URLs in M3U8 to point back through the proxy."""
        lines = content.decode("utf-8", errors="ignore").splitlines()
        new_lines = []
        
        # Determine the base directory of the current M3U8
        base_parts = base_url.rsplit("/", 1)
        base_dir = base_parts[0] + "/" if len(base_parts) > 1 else ""

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                new_lines.append(line)
            else:
                # This is a URL (segment or sub-playlist)
                abs_url = line
                if not line.startswith("http"):
                    abs_url = urllib.parse.urljoin(base_dir, line)
                
                # Point it back to our proxy
                proxy_url = f"/proxy?url={urllib.parse.quote(abs_url)}"
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
        self.server = socketserver.TCPServer(("127.0.0.1", self.port), handler)
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
        return f"http://127.0.0.1:{self.port}/proxy?url={urllib.parse.quote(target_url)}"
