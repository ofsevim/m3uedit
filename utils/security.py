"""URL and address policy shared by imports, probes and streaming."""

import ipaddress
import re
import socket
from urllib.parse import urlsplit


def validate_url(url: str):
    if not isinstance(url, str) or re.search(r'[\s<>"\\\x00-\x1f\x7f]', url):
        raise ValueError("URL geçersiz karakter içeriyor.")
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Yalnızca HTTP/HTTPS adresleri kullanılabilir.")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URL içinde kullanıcı bilgisi desteklenmiyor.")
        _ = parsed.port
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Geçerli bir HTTP/HTTPS adresi girin.") from exc
    return parsed


def resolve_addresses(host: str, port: int, *, allow_private: bool = False):
    """Reject mixed public/private answers as well as IPv4-mapped IPv6."""
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not allow_private:
        address = getattr(literal, "ipv4_mapped", None) or literal
        if not address.is_global:
            raise ValueError("Yerel/özel ağ adreslerine erişim kapalı.")
    answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not answers:
        raise ValueError("Adres çözümlenemedi.")
    for answer in answers:
        address = ipaddress.ip_address(answer[4][0].split("%", 1)[0])
        address = getattr(address, "ipv4_mapped", None) or address
        if not allow_private and not address.is_global:
            raise ValueError("Yerel/özel ağ adreslerine erişim kapalı.")
    return answers


def validate_target(url: str, *, allow_private: bool = False):
    parsed = validate_url(url)
    resolve_addresses(
        parsed.hostname,
        parsed.port or (443 if parsed.scheme == "https" else 80),
        allow_private=allow_private,
    )
    return parsed


def validate_proxy(url: str | None):
    """An explicitly configured upstream is trusted and may be loopback."""
    if not url:
        return None
    validate_url(url)
    return url
