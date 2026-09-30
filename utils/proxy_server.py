"""Authenticated streaming gateway with isolated per-session state."""

import atexit
import http.server
import os
import re
import secrets
import socketserver
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import weakref
from pathlib import Path

from utils import config, network
from utils.security import validate_proxy, validate_target, validate_url

CHUNK_SIZE = 64 * 1024
_gateway = None
_gateway_lock = threading.RLock()


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sessions = weakref.WeakValueDictionary()
        self.slots = threading.BoundedSemaphore(32)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        request.settimeout(15)
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        # URLs include provider credentials and session capability tokens.
        pass

    def _cors(self):
        origin = self.headers.get("Origin", "")
        parsed = urllib.parse.urlsplit(origin)
        if origin and (
            origin == config.PROXY_ALLOWED_ORIGIN
            or (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1"))
        ):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Accept")
        self.send_header(
            "Access-Control-Expose-Headers", "Content-Length, Content-Range, Accept-Ranges"
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")

    def _error(self, status):
        self.send_response(status)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _authorize(self):
        if len(self.path) > 16384:
            self._error(414)
            return None
        parsed = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parsed.query, max_num_fields=10)
        token = query.get("token", [""])[0]
        with _gateway_lock:
            instance = self.server.sessions.get(token)
        if not instance or not secrets.compare_digest(token, instance.token):
            self._error(403)
            return None
        self.instance = instance
        return parsed, query

    def do_OPTIONS(self):
        if self._authorize():
            self._error(204)

    def do_HEAD(self):
        self._handle_request(False)

    def do_GET(self):
        self._handle_request(True)

    def _handle_request(self, send_body):
        headers_sent = False
        try:
            authorized = self._authorize()
            if not authorized:
                return
            parsed, query = authorized
            instance = self.instance
            if parsed.path in ("/playlist", "/playlist.m3u", "/proxied_playlist.m3u"):
                filename = (
                    instance.proxied_playlist_file
                    if "proxied" in parsed.path
                    else instance.playlist_file
                )
                # Windows does not permit replacing an open file: serialize reads and writes.
                try:
                    with instance.lock, open(filename, "rb") as stream:
                        body = stream.read()
                except FileNotFoundError:
                    self._error(404)
                    return
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/x-mpegurl; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                headers_sent = True
                if send_body:
                    self.wfile.write(body)
                return
            if parsed.path != "/proxy":
                self._error(404)
                return
            target = query.get("url", [""])[0]
            validate_target(target, allow_private=instance.allow_private_networks)
            with instance.lock:
                ua, referer, upstream = (
                    instance.custom_user_agent,
                    instance.custom_referer,
                    instance.upstream_proxy,
                )
            headers = {"User-Agent": ua or config.USER_AGENT}
            for key in ("Range", "Accept"):
                if self.headers.get(key):
                    headers[key] = self.headers[key]
            # Use the provider referer, never the application's own iframe origin.
            if referer:
                headers["Referer"] = referer
            request = urllib.request.Request(
                target, headers=headers, method="GET" if send_body else "HEAD"
            )
            with network.open_url(
                request,
                timeout=config.REQUEST_TIMEOUT,
                proxy_url=upstream,
                allow_private=instance.allow_private_networks,
            ) as response:
                final = response.url
                content_type = response.getheader("Content-Type", "application/octet-stream")
                manifest = "mpegurl" in content_type.lower() or urllib.parse.urlsplit(
                    final
                ).path.lower().endswith(".m3u8")
                body = None
                if manifest and send_body:
                    body = self.rewrite_m3u8(
                        network.read_bounded(response, config.MAX_MANIFEST_BYTES), final
                    )
                self.send_response(response.status)
                self._cors()
                self.send_header(
                    "Content-Type", "application/vnd.apple.mpegurl" if manifest else content_type
                )
                if body is not None:
                    self.send_header("Content-Length", str(len(body)))
                elif not manifest:
                    for key in ("Content-Length", "Content-Range", "Accept-Ranges"):
                        if response.getheader(key):
                            self.send_header(key, response.getheader(key))
                self.end_headers()
                headers_sent = True
                if send_body:
                    if body is not None:
                        self.wfile.write(body)
                    else:
                        while chunk := response.read(CHUNK_SIZE):
                            self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except urllib.error.HTTPError as exc:
            exc.close()
            if not headers_sent:
                self._error(exc.code)
        except ValueError:
            if not headers_sent:
                self._error(400)
        except (OSError, urllib.error.URLError):
            if not headers_sent:
                self._error(502)
        except Exception:
            if not headers_sent:
                self._error(502)

    _uri_re = re.compile(r'(URI\s*=\s*")([^"]+)(")', re.IGNORECASE)

    def _make_proxy_url(self, url):
        # Root-relative URLs preserve the trusted browser/TV authority and HTTPS.
        prefix = (
            urllib.parse.urlsplit(config.PROXY_PUBLIC_BASE_URL).path.rstrip("/")
            if config.PROXY_PUBLIC_BASE_URL
            else ""
        )
        return f"{prefix}/proxy?token={self.instance.token}&url={urllib.parse.quote(url, safe='')}"

    def _resolve_url(self, base_url, url):
        resolved = urllib.parse.urljoin(base_url, url)
        base, target = urllib.parse.urlsplit(base_url), urllib.parse.urlsplit(resolved)
        # Propagate provider tokens only within the same authority.
        if base.query and not target.query and base.netloc == target.netloc:
            resolved = urllib.parse.urlunsplit(target._replace(query=base.query))
        validate_url(resolved)
        return resolved

    def rewrite_m3u8(self, content, base_url):
        lines = []
        for line in content.decode("utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("#"):
                line = self._uri_re.sub(
                    lambda m: m[1] + self._make_proxy_url(self._resolve_url(base_url, m[2])) + m[3],
                    line,
                )
            elif line:
                line = self._make_proxy_url(self._resolve_url(base_url, line))
            lines.append(line)
        return "\n".join(lines).encode("utf-8")


class LocalProxyServer:
    """One session's settings/files; the gateway routes by unguessable token."""

    def __init__(self, *, allow_private_networks=None):
        self.server = self.thread = self.port = None
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.upstream_proxy = self.custom_user_agent = self.custom_referer = None
        self.allow_private_networks = (
            config.ALLOW_PRIVATE_NETWORKS
            if allow_private_networks is None
            else allow_private_networks
        )
        self.directory = tempfile.TemporaryDirectory(prefix="m3uedit-session-")
        self.playlist_file = str(Path(self.directory.name) / "playlist.m3u")
        self.proxied_playlist_file = str(Path(self.directory.name) / "proxied_playlist.m3u")
        self.content_digest = None

    def set_proxy_config(self, upstream_proxy=None, custom_user_agent=None, custom_referer=None):
        upstream = validate_proxy(upstream_proxy.strip() if upstream_proxy else None)
        referer = custom_referer.strip() if custom_referer else None
        if referer:
            validate_url(referer)
        ua = custom_user_agent.strip() if custom_user_agent else None
        if ua and any(ord(c) < 32 or ord(c) == 127 for c in ua):
            raise ValueError("User-Agent geçersiz karakter içeriyor.")
        with self.lock:
            self.upstream_proxy, self.custom_user_agent, self.custom_referer = upstream, ua, referer

    def start(self):
        global _gateway
        with _gateway_lock:
            if self.server:
                return self.port
            if _gateway is None:
                server = ThreadingTCPServer(
                    (config.PROXY_BIND_HOST, config.PROXY_PORT), ProxyHandler
                )
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                _gateway = server, thread
            self.server, self.thread = _gateway
            self.port = self.server.server_address[1]
            self.server.sessions[self.token] = self
            return self.port

    def stop(self):
        global _gateway
        with _gateway_lock:
            if self.server:
                self.server.sessions.pop(self.token, None)
                if not self.server.sessions:
                    self.server.shutdown()
                    self.server.server_close()
                    _gateway = None
                self.server = self.thread = self.port = None
        with self.lock:
            self.directory.cleanup()

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

    def endpoint_url(self, path, *, host="127.0.0.1", public=False):
        base = (
            config.PROXY_PUBLIC_BASE_URL
            if public and config.PROXY_PUBLIC_BASE_URL
            else f"http://{host}:{self.port}"
        )
        return f"{base}/{path.lstrip('/')}?token={self.token}"

    def get_proxy_url(self, target_url, host="127.0.0.1", *, public=False):
        return f"{self.endpoint_url('proxy', host=host, public=public)}&url={urllib.parse.quote(target_url, safe='')}"

    def set_m3u_content(self, content: str, proxied_content: str = ""):
        # Digest avoids repeated disk writes on Streamlit reruns.
        import hashlib

        if any(
            len(text.encode("utf-8")) > config.MAX_FILE_SIZE_MB * 1024 * 1024
            for text in (content, proxied_content)
        ):
            raise ValueError("Dosya boyutu sınırı aşıldı.")
        digest = hashlib.sha256((content + "\0" + proxied_content).encode("utf-8")).digest()
        with self.lock:
            if digest == self.content_digest:
                return
            for destination, text in (
                (self.playlist_file, content),
                (self.proxied_playlist_file, proxied_content),
            ):
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", newline="", dir=self.directory.name, delete=False
                ) as stream:
                    staged = stream.name
                    stream.write(text)
                try:
                    os.replace(staged, destination)
                finally:
                    if os.path.exists(staged):
                        os.unlink(staged)
            self.content_digest = digest


def _shutdown_gateway():
    global _gateway
    with _gateway_lock:
        if _gateway:
            server, _ = _gateway
            for instance in list(server.sessions.values()):
                instance.directory.cleanup()
            server.shutdown()
            server.server_close()
            _gateway = None


atexit.register(_shutdown_gateway)
