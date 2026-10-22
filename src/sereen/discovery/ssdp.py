"""SSDP (UPnP) discovery.

Many Epson projectors advertise themselves over SSDP.  This is a generic
implementation of the M-SEARCH probe; the projector-specific parsing happens
in the protocol layer.
"""

from __future__ import annotations

import socket
import struct
from collections.abc import Iterable

from ..models import Projector, Protocol

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900

M_SEARCH = (
    "M-SEARCH * HTTP/1.1\r\n"
    "HOST: 239.255.255.250:1900\r\n"
    'MAN: "ssdp:discover"\r\n'
    "MX: 2\r\n"
    "ST: ssdp:all\r\n"
    "\r\n"
)


def discover_ssdp(timeout: float = 3.0, retries: int = 2) -> list[Projector]:
    """Send an SSDP M-SEARCH and collect responding projectors."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.0)
    except OSError:  # pragma: no cover - platform dependent
        pass

    found: list[Projector] = []
    seen: set[str] = set()
    try:
        for _ in range(max(1, retries)):
            try:
                sock.sendto(M_SEARCH.encode("ascii"), (SSDP_ADDR, SSDP_PORT))
            except OSError:
                break
            deadline = _monotonic() + timeout
            while _monotonic() < deadline:
                try:
                    data, addr = sock.recvfrom(65535)
                except socket.timeout:
                    break
                except OSError:
                    break
                projector = _parse_ssdp(data, addr[0])
                if projector is None or projector.host in seen:
                    continue
                seen.add(projector.host)
                found.append(projector)
    finally:
        sock.close()
    return found


def _parse_ssdp(data: bytes, source: str) -> Projector | None:
    """Turn an SSDP response into a Projector, if it looks like a projector."""
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover - defensive
        return None

    headers: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()

    server = headers.get("usn", "") + headers.get("server", "") + headers.get("st", "")
    location = headers.get("location", "")
    if not _mentions_projector(server + " " + location + " " + text):
        return None

    return Projector(
        host=source,
        port=4352,
        protocol=Protocol.UNKNOWN,
        name=headers.get("friendlyname") or None,
        extras={k: v for k, v in headers.items() if k.startswith("x-") or k == "location"},
    )


_PROJECTOR_WORDS = ("epson", "projector", "beamer", "pjlink", "esc/vp", "escvp")


def _mentions_projector(text: str) -> bool:
    low = text.lower()
    return any(word in low for word in _PROJECTOR_WORDS)


def _monotonic() -> float:
    import time

    return time.monotonic()


__all__ = ["discover_ssdp", "SSDP_ADDR", "SSDP_PORT"]
