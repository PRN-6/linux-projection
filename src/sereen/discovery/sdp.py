"""Epson "Simple Projector" (SDP) UDP discovery.

Epson projectors answer a UDP broadcast probe and reply with a small binary
blob that carries the projector's name, model and MAC addresses.  The exact
layout of that blob is not publicly documented, so the parser here is
deliberately tolerant: it looks for the pieces of information it needs
(ASCII strings, MAC addresses, a model-like token) instead of depending on
byte offsets that may differ between firmware revisions.

The probe itself is sent to the broadcast address on the SDP port; a reply
from any address is treated as a projector.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any

from ..models import Projector, Protocol

SDP_PORT = 9170
BROADCAST = "255.255.255.255"

#: Probe payloads to try.  Projectors have been observed to answer more than
#: one variant, so we send all of them rather than guessing the single
#: "correct" one.
_PROBES: tuple[bytes, ...] = (
    b"EPSON",
    b"Projector",
    b"\x00\x00\x00\x00",
    b"SDP",
)


def _broadcast_addresses() -> list[str]:
    """Broadcast address of every local interface."""
    from .. import netutil

    addrs: list[str] = []
    for net in netutil.local_networks():
        if net.prefixlen >= 31 or net.is_loopback:
            continue
        if net.overlaps(ipaddress.ip_network("169.254.0.0/16")):
            continue
        try:
            addrs.append(str(net.broadcast_address))
        except ValueError:  # pragma: no cover - defensive
            continue
    return addrs or [BROADCAST]


def discover_sdp(timeout: float = 2.0, retries: int = 2) -> list[Projector]:
    """Broadcast an SDP probe and collect the projectors that answer."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError:  # pragma: no cover - defensive
        return []
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.5)
    except OSError:  # pragma: no cover - platform dependent
        pass

    targets = [(addr, SDP_PORT) for addr in _broadcast_addresses()]
    found: dict[str, Projector] = {}

    try:
        for _ in range(max(1, retries)):
            for probe in _PROBES:
                for target in targets:
                    try:
                        sock.sendto(probe, target)
                    except OSError:
                        continue
            deadline = _monotonic() + timeout
            while _monotonic() < deadline:
                try:
                    data, addr = sock.recvfrom(65535)
                except socket.timeout:
                    break
                except OSError:
                    break
                host = addr[0]
                if host in found:
                    continue
                projector = _parse_sdp(data, host)
                if projector is not None:
                    found[host] = projector
    finally:
        sock.close()

    return list(found.values())


_MAC_RE = re.compile(rb"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")
_PRINTABLE_RE = re.compile(rb"[ -~]{4,}")


def _looks_like_mac(raw: bytes) -> bool:
    """A plausible unicast MAC address in raw binary form."""
    if len(raw) != 6 or raw in (b"\x00" * 6, b"\xff" * 6):
        return False
    # Skip text: an ASCII string like "00:11:22" would otherwise look like a
    # perfectly good binary MAC.
    if all(0x20 <= b <= 0x7E for b in raw):
        return False
    if b":" in raw or b"-" in raw:
        return False
    # A unicast address has the least significant bit of the first octet clear.
    return not raw[0] & 0x01


def _extract_macs(data: bytes) -> list[str]:
    """Pull MAC addresses out of a payload, in text or raw binary form."""
    macs = [m.group().decode("ascii", "replace") for m in _MAC_RE.finditer(data)]
    for index in range(len(data) - 5):
        chunk = data[index : index + 6]
        if _looks_like_mac(chunk):
            macs.append(":".join(f"{b:02X}" for b in chunk))
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for mac in macs:
        if mac not in seen:
            seen.add(mac)
            unique.append(mac)
    return unique


def _parse_sdp(data: bytes, host: str) -> Projector | None:
    """Best-effort extraction of projector details from an SDP reply."""
    if not data:
        return None
    strings = [m.group().decode("ascii", "replace") for m in _PRINTABLE_RE.finditer(data)]
    macs = _extract_macs(data)

    joined = " ".join(strings).lower()
    if not any(word in joined for word in ("epson", "projector", "pdl", "esc")):
        # Unknown vendor reply - still a projector candidate, but we have no
        # name for it.
        if not macs:
            return None

    name = None
    model = None
    manufacturer = None
    for text in strings:
        low = text.lower()
        if "epson" in low:
            manufacturer = "Epson"
        if low.startswith("model") or re.match(r"^[A-Z]{2}[-]?\d{3}", text):
            model = text
        if low.startswith("name") or "name=" in low:
            name = text.split("=", 1)[-1] if "=" in text else text
    if manufacturer is None and "epson" in joined:
        manufacturer = "Epson"

    extras: dict[str, Any] = {}
    if macs:
        extras["mac_addresses"] = macs
    if strings:
        extras["sdp_strings"] = strings

    return Projector(
        host=host,
        port=4352,
        protocol=Protocol.UNKNOWN,
        name=name,
        model=model,
        manufacturer=manufacturer,
        extras=extras,
    )


def _monotonic() -> float:
    import time

    return time.monotonic()


__all__ = ["discover_sdp", "SDP_PORT"]
