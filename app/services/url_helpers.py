from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit


_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def normalize_server_base_url(raw_value: str | None) -> str | None:
    value = (raw_value or "").strip().rstrip("/")
    if not value:
        return None
    if _SCHEME_RE.match(value):
        return value

    host = value.split("/", 1)[0]
    scheme = "https"
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback:
            scheme = "http"
    except ValueError:
        if host == "localhost":
            scheme = "http"

    return f"{scheme}://{value}"


def google_oauth_origin(base_url: str | None) -> str | None:
    normalized = normalize_server_base_url(base_url)
    if not normalized:
        return None
    parts = urlsplit(normalized)
    return f"{parts.scheme}://{parts.netloc}"


def google_oauth_redirect_uri_from_base_url(base_url: str | None) -> str | None:
    origin = google_oauth_origin(base_url)
    if not origin:
        return None
    return f"{origin}/google/oauth/callback"
