"""Custom inference endpoint policy for MaryV2 13.63.

Remote custom endpoints are untrusted configuration. Cloud metadata, link-local,
unspecified and multicast destinations are always rejected. Loopback/private
LAN endpoints remain opt-in because Mary's local engines legitimately use them.
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

VERSION = "13.63"
_BLOCKED_HOSTS = {"metadata.google.internal", "metadata.google", "instance-data.ec2.internal"}


def validate_endpoint(url: str, *, allow_local: bool = False) -> str:
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("endpoint must be an http(s) URL with a hostname")
    host = parsed.hostname.rstrip(".").lower()
    if host in _BLOCKED_HOSTS or host.endswith(".metadata.google.internal"):
        raise ValueError("cloud metadata endpoints are forbidden")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # DNS rebinding protection also belongs at connection time after DNS
        # resolution. This validator intentionally does not perform DNS I/O.
        return str(url).strip()
    if ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        raise ValueError("unsafe endpoint address")
    if (ip.is_loopback or ip.is_private) and not allow_local:
        raise ValueError("local/private endpoint requires explicit allow_local")
    return str(url).strip()


def resolved_address_allowed(address: str, *, allow_local: bool = False) -> bool:
    """Connection-time check for every resolved address (DNS-rebinding seam)."""
    try:
        ip = ipaddress.ip_address(str(address).strip())
    except ValueError:
        return False
    if ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        return False
    if (ip.is_loopback or ip.is_private) and not allow_local:
        return False
    return True
