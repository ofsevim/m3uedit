"""Network helpers for playlist fetching and share-link creation."""

from __future__ import annotations

import ssl
import urllib.parse
import urllib.request


def create_ssl_context(disable_ssl_verify: bool) -> ssl.SSLContext:
    """Build an SSL context based on the current trust policy."""
    context = ssl.create_default_context()
    if disable_ssl_verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def fetch_m3u_source(
    url: str,
    *,
    user_agent: str,
    timeout: int,
    disable_ssl_verify: bool,
) -> list[bytes]:
    """Download a playlist and return its raw lines."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    context = create_ssl_context(disable_ssl_verify)
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return response.readlines()


def create_m3u_link(
    m3u_content: str,
    *,
    user_agent: str,
    disable_ssl_verify: bool,
    timeout: int = 15,
) -> str:
    """Upload filtered M3U content to a paste service and return a raw URL."""
    context = create_ssl_context(disable_ssl_verify)

    try:
        request = urllib.request.Request(
            "https://paste.rs/",
            data=m3u_content.encode("utf-8"),
            headers={"User-Agent": user_agent, "Content-Type": "text/plain"},
        )
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            paste_url = response.read().decode("utf-8").strip()
            if paste_url.startswith("http"):
                return paste_url
    except Exception:
        pass

    try:
        data = urllib.parse.urlencode(
            {
                "content": m3u_content,
                "syntax": "text",
                "expiry_days": 365,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            "https://dpaste.com/api/v2/",
            data=data,
            headers={"User-Agent": user_agent},
        )
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            paste_url = response.read().decode("utf-8").strip().strip('"')
            if paste_url and not paste_url.endswith(".txt"):
                paste_url = paste_url.rstrip("/") + ".txt"
            return paste_url
    except Exception:
        return ""
