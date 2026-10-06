"""Bounded downloads with consistent TLS, redirect and address policies."""

import functools
import http.client
import secrets
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from utils import config
from utils.security import resolve_addresses, validate_proxy, validate_target, validate_url


def create_ssl_context(disable_ssl_verify: bool = False) -> ssl.SSLContext:
    context = ssl.create_default_context()
    if disable_ssl_verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _connect(
    address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, *, allow_private=False
):
    """Connect to the exact approved DNS answer, without a second DNS lookup."""
    failure = None
    for family, socktype, proto, _, sockaddr in resolve_addresses(
        *address, allow_private=allow_private
    ):
        sock = socket.socket(family, socktype, proto)
        try:
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            failure = exc
            sock.close()
    raise failure or OSError("Bağlantı kurulamadı.")


class _HTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args, allow_private=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = functools.partial(_connect, allow_private=allow_private)


class _HTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, allow_private=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = functools.partial(_connect, allow_private=allow_private)


class _HTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, allow_private):
        super().__init__()
        self.allow_private = allow_private

    def http_open(self, req):
        return self.do_open(
            functools.partial(_HTTPConnection, allow_private=self.allow_private), req
        )


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, context, allow_private):
        super().__init__(context=context)
        self.allow_private = allow_private

    def https_open(self, req):
        return self.do_open(
            functools.partial(_HTTPSConnection, allow_private=self.allow_private),
            req,
            context=self._context,
        )


class _RedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow_private):
        self.allow_private = allow_private

    def http_error_302(self, req, fp, code, msg, headers):
        class UndrainedResponse:
            def read(self, *args):
                return b""

            def close(self):
                fp.close()

            def __getattr__(self, name):
                return getattr(fp, name)

        try:
            return super().http_error_302(req, UndrainedResponse(), code, msg, headers)
        finally:
            fp.close()

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_target(newurl, allow_private=self.allow_private)
        if urllib.parse.urlsplit(req.full_url).scheme == "https" and newurl.startswith("http:"):
            raise ValueError("HTTPS adresinden HTTP adresine yönlendirme engellendi.")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if (
            redirected
            and urllib.parse.urlsplit(req.full_url).netloc != urllib.parse.urlsplit(newurl).netloc
        ):
            for key in ("Authorization", "Cookie", "Referer"):
                redirected.remove_header(key)
        return redirected


def open_url(request, *, timeout=30, disable_ssl_verify=None, proxy_url=None, allow_private=None):
    allow_private = config.ALLOW_PRIVATE_NETWORKS if allow_private is None else allow_private
    disable_ssl_verify = (
        config.DISABLE_SSL_VERIFY if disable_ssl_verify is None else disable_ssl_verify
    )
    if isinstance(request, str):
        request = urllib.request.Request(request)
    validate_target(request.full_url, allow_private=allow_private)
    validate_proxy(proxy_url)
    context = create_ssl_context(disable_ssl_verify)
    handlers = [
        urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url} if proxy_url else {}),
        _RedirectHandler(allow_private),
    ]
    if proxy_url:
        # This proxy is explicitly chosen by the user; its egress DNS is trusted.
        handlers.extend(
            [urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(context=context)]
        )
    else:
        handlers.extend([_HTTPHandler(allow_private), _HTTPSHandler(context, allow_private)])
    return urllib.request.build_opener(*handlers).open(request, timeout=timeout)


def read_bounded(response, max_bytes: int, *, deadline_seconds: float = 30) -> bytes:
    """Read bounded chunks, even when a hostile response has one huge line."""
    length = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
    if length:
        try:
            oversized = int(length) > max_bytes
        except ValueError:
            oversized = False
        if oversized:
            raise ValueError("Dosya boyutu sınırı aşıldı.")
    parts, size = [], 0
    deadline = time.monotonic() + deadline_seconds
    read = getattr(response, "read1", response.read)
    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
    socket_timeout = sock.gettimeout() if sock else None
    deadline_interrupted = threading.Event()

    def interrupt():
        # A chunk-size/trailer line can drip forever inside HTTPResponse.readline.
        # Shutdown wakes that read even if individual bytes never hit its socket timeout.
        # Windows timers can fire just before monotonic() reaches the deadline.
        deadline_interrupted.set()
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    timer = threading.Timer(max(0, deadline_seconds), interrupt) if sock else None
    if timer:
        timer.daemon = True
        timer.start()
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("İndirme süresi sınırı aşıldı.")
            if sock and sock.fileno() >= 0:
                sock.settimeout(min(socket_timeout, remaining) if socket_timeout else remaining)
            try:
                chunk = read(min(64 * 1024, max_bytes - size + 1))
            except (OSError, http.client.HTTPException) as exc:
                if deadline_interrupted.is_set() or time.monotonic() >= deadline:
                    raise TimeoutError("İndirme süresi sınırı aşıldı.") from exc
                raise
            if deadline_interrupted.is_set() or time.monotonic() >= deadline:
                raise TimeoutError("İndirme süresi sınırı aşıldı.")
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("Dosya boyutu sınırı aşıldı.")
            parts.append(chunk)
        return b"".join(parts)
    finally:
        if timer:
            timer.cancel()


def fetch_m3u_source(
    url: str,
    *,
    user_agent: str,
    timeout: int,
    disable_ssl_verify: bool = False,
    proxy_url=None,
    headers=None,
) -> list[bytes]:
    validate_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, **(headers or {})})
    with open_url(
        request, timeout=timeout, disable_ssl_verify=disable_ssl_verify, proxy_url=proxy_url
    ) as response:
        return read_bounded(
            response, config.MAX_FILE_SIZE_MB * 1024 * 1024, deadline_seconds=timeout
        ).splitlines(keepends=True)


PASTE_RS_MAX_BYTES = 64 * 1024
DPASTE_MAX_BYTES = 1000 * 1000
_SHARE_HOSTS = {
    "paste.rs": ("paste.rs",),
    "dpaste.com": ("dpaste.com",),
    "catbox.moe": ("catbox.moe", "files.catbox.moe"),
}


def _encode_multipart(
    fields: dict[str, str],
    file_field: tuple[str, str, bytes, str] | None = None,
) -> tuple[bytes, str]:
    boundary = f"----M3UEditBoundary{secrets.token_hex(16)}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode("utf-8")
        )
    if file_field is not None:
        field_name, filename, content, content_type = file_field
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
            + content
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def create_m3u_link(
    m3u_content: str,
    *,
    user_agent: str,
    disable_ssl_verify=False,
    timeout=30,
    service="dpaste.com",
    consent=False,
    proxy_url=None,
) -> str:
    """Explicit, verified HTTPS publishing; never silently switch services."""
    if not consent:
        raise ValueError("Harici paylaşım için açık onay gerekli.")
    if not m3u_content or not m3u_content.strip():
        raise ValueError("Paylaşılacak M3U içeriği boş.")
    raw_bytes = m3u_content.encode("utf-8")
    max_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise ValueError("Dosya boyutu sınırı aşıldı.")
    if service == "paste.rs":
        if len(raw_bytes) > PASTE_RS_MAX_BYTES:
            raise ValueError(
                "Liste boyutu paste.rs sınırını (64 KB) aşıyor. "
                "Lütfen dpaste.com veya catbox.moe servisini seçin."
            )
        url = "https://paste.rs/"
        data = raw_bytes
        headers = {"Content-Type": "text/plain; charset=utf-8"}
    elif service == "dpaste.com":
        if len(raw_bytes) > DPASTE_MAX_BYTES:
            raise ValueError(
                "Liste boyutu dpaste.com sınırını (1 MB) aşıyor. "
                "Daha büyük listeler için catbox.moe servisini seçin."
            )
        url = "https://dpaste.com/api/v2/"
        data, content_type = _encode_multipart(
            {"syntax": "text", "expiry_days": "1", "content": m3u_content}
        )
        headers = {"Content-Type": content_type}
    elif service == "catbox.moe":
        url = "https://catbox.moe/user/api.php"
        data, content_type = _encode_multipart(
            {"reqtype": "fileupload"},
            ("fileToUpload", "playlist.m3u", raw_bytes, "audio/x-mpegurl"),
        )
        headers = {"Content-Type": content_type}
    else:
        raise ValueError("Desteklenmeyen paylaşım servisi.")
    if len(data) > max_bytes + 4096:
        raise ValueError("Dosya boyutu sınırı aşıldı.")
    request = urllib.request.Request(url, data=data, headers={"User-Agent": user_agent, **headers})
    open_kwargs = {"timeout": timeout, "disable_ssl_verify": False, "allow_private": False}
    if proxy_url:
        open_kwargs["proxy_url"] = proxy_url
    # Publishing always verifies TLS, even if a local IPTV source opted out.
    try:
        with open_url(request, **open_kwargs) as response:
            status = getattr(response, "status", 200)
            link = (
                read_bounded(response, 4096, deadline_seconds=timeout).decode().strip().strip('"')
            )
            if status == 206:
                raise ValueError(
                    f"{service} içeriği eksik kaydetti (boyut sınırı aşıldı). "
                    "Lütfen dpaste.com veya catbox.moe servisini seçin."
                )
    except urllib.error.HTTPError as exc:
        exc.close()
        if exc.code == 413:
            raise ValueError(
                f"Liste boyutu {service} servisinin kabul ettiği sınırı aşıyor (HTTP 413)."
            ) from exc
        if exc.code in (429, 503):
            raise OSError(
                f"{service} servisi şu anda yoğun veya hız sınırına takıldı (HTTP {exc.code}). "
                "Farklı bir paylaşım servisi seçip tekrar deneyin."
            ) from exc
        raise OSError(
            f"{service} servisi isteği reddetti (HTTP {exc.code}). "
            "Farklı bir paylaşım servisi seçip tekrar deneyin."
        ) from exc
    parsed = validate_url(link)
    if parsed.scheme != "https" or parsed.hostname not in _SHARE_HOSTS[service]:
        raise ValueError("Paylaşım servisi geçersiz bağlantı döndürdü.")
    if service == "dpaste.com" and not link.endswith(".txt"):
        link = link.rstrip("/") + ".txt"
    return link

