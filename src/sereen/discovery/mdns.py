"""mDNS / DNS-SD discovery.

A small, dependency-free multicast DNS resolver.  It queries the standard
service types that projectors tend to advertise and turns the answers into
:class:`~sereen.models.Projector` instances.

Supported service types:

``_pdl-datastream._tcp``
    Epson "PDL" (Projector Data Link) - Epson's own screen/data service.
``_usleep._tcp``
    Epson USB/network projection ("Wireless Presentation") service.
``_airplay._tcp`` / ``_raop._tcp``
    AirPlay receivers, which some projectors implement for mirroring.
``_ipp._tcp`` / ``_printer._tcp``
    Not projectors, but cheap to check on the same wire.
"""

from __future__ import annotations

import enum
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Any

from ..models import Projector, Protocol

MDNS_ADDR = "224.0.0.251"
MDNS_PORT = 5353

SERVICE_TYPES = (
    "_pdl-datastream._tcp.local",
    "_usleep._tcp.local",
    "_airplay._tcp.local",
    "_raop._tcp.local",
    "_ipp._tcp.local",
)


class _Type(enum.IntEnum):
    A = 1
    PTR = 12
    TXT = 16
    AAAA = 28
    SRV = 33
    ANY = 255


@dataclass
class _Resource:
    name: str
    rtype: int
    rclass: int
    ttl: int
    data: bytes = b""

    @property
    def is_unique(self) -> bool:
        return bool(self.rclass & 0x8000)


@dataclass
class MDNSResult:
    """Everything we learned about one responder."""

    host: str
    port: int = 0
    names: list[str] = field(default_factory=list)
    txt: dict[str, str] = field(default_factory=dict)
    addresses: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)


def _encode_name(name: str) -> bytes:
    out = bytearray()
    for label in name.rstrip(".").split("."):
        if not label:
            continue
        raw = label.encode("idna" if any(ord(c) > 127 for c in label) else "ascii")
        out.append(len(raw))
        out += raw
    out.append(0)
    return bytes(out)


def _decode_name(data: bytes, offset: int) -> tuple[str, int]:
    """Decode a (possibly compressed) DNS name; returns (name, new offset)."""
    labels: list[str] = []
    jumped = False
    end = offset
    seen: set[int] = set()
    while offset < len(data):
        length = data[offset]
        if length == 0:
            offset += 1
            if not jumped:
                end = offset
            break
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                break
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                end = offset + 2
            jumped = True
            if pointer in seen:  # compression loop guard
                break
            seen.add(pointer)
            offset = pointer
            continue
        offset += 1
        labels.append(data[offset : offset + length].decode("utf-8", "replace"))
        offset += length
        if not jumped:
            end = offset
    if not jumped:
        end = offset
    return ".".join(labels), end


def _parse_message(data: bytes) -> list[_Resource]:
    if len(data) < 12:
        return []
    _tid, _flags, qdcount, ancount, nscount, arcount = struct.unpack("!6H", data[:12])
    offset = 12
    resources: list[_Resource] = []

    for _ in range(qdcount):
        name, offset = _decode_name(data, offset)
        if offset + 4 > len(data):
            break
        qtype, qclass = struct.unpack("!HH", data[offset : offset + 4])
        offset += 4
        resources.append(_Resource(name=name, rtype=qtype, rclass=qclass, ttl=0))

    total = ancount + nscount + arcount
    for _ in range(total):
        if offset >= len(data):
            break
        name, offset = _decode_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset : offset + 10])
        offset += 10
        rdata = data[offset : offset + rdlength]
        offset += rdlength
        resources.append(
            _Resource(name=name, rtype=rtype, rclass=rclass, ttl=ttl, data=rdata)
        )
    return resources


def _parse_txt(rdata: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    index = 0
    while index < len(rdata):
        length = rdata[index]
        index += 1
        if length == 0:
            continue
        chunk = rdata[index : index + length]
        index += length
        if b"=" in chunk:
            key, _, value = chunk.partition(b"=")
            out[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
        else:
            out[chunk.decode("utf-8", "replace")] = ""
    return out


def _build_query(service_types: tuple[str, ...], delay: float) -> bytes:
    """Build an mDNS query packet (one question per service type)."""
    header = struct.pack("!6H", 0, 0, len(service_types), 0, 0, 0)
    questions = b""
    for stype in service_types:
        questions += _encode_name(stype) + struct.pack("!HH", _Type.PTR, 0x0001)
    return header + questions


def _interface_addresses() -> list[str]:
    """Local IPv4 addresses used to bind the multicast socket."""
    addrs: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addr = info[4][0]
            if not addr.startswith("127.") and addr not in addrs:
                addrs.append(addr)
    except OSError:
        pass
    if not addrs:
        addrs = ["0.0.0.0"]
    return addrs


def discover_mdns(
    timeout: float = 3.0,
    service_types: tuple[str, ...] = SERVICE_TYPES,
) -> list[Projector]:
    """Query mDNS for the given service types and return matching projectors."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEPORT, 1
            )
        except (AttributeError, OSError):  # pragma: no cover - platform dependent
            pass
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        except OSError:  # pragma: no cover - platform dependent
            pass
        sock.bind(("", MDNS_PORT))
        sock.settimeout(0.5)
    except OSError:
        sock.close()
        return []

    query = _build_query(service_types, 0.0)
    responders: dict[str, MDNSResult] = {}

    try:
        for addr in _interface_addresses():
            try:
                sock.sendto(query, (MDNS_ADDR, MDNS_PORT))
            except OSError:
                continue
            break  # one send is enough - it goes out of the default route

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, source = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            _ingest(data, source[0], responders)
    finally:
        sock.close()

    return _to_projectors(responders)


def _ingest(data: bytes, source: str, responders: dict[str, MDNSResult]) -> None:
    for resource in _parse_message(data):
        if resource.rtype == _Type.SRV and len(resource.data) >= 6:
            priority, weight, port = struct.unpack("!HHH", resource.data[:6])
            target, _ = _decode_name(resource.data, 6)
            entry = responders.setdefault(source, MDNSResult(host=source))
            entry.port = port
            if target:
                entry.names.append(target)
        elif resource.rtype == _Type.TXT:
            entry = responders.setdefault(source, MDNSResult(host=source))
            entry.txt.update(_parse_txt(resource.data))
        elif resource.rtype == _Type.PTR:
            entry = responders.setdefault(source, MDNSResult(host=source))
            target, _ = _decode_name(resource.data, 0)
            if target:
                entry.services.append(target)
        elif resource.rtype == _Type.A and len(resource.data) == 4:
            entry = responders.setdefault(source, MDNSResult(host=source))
            ip = socket.inet_ntoa(resource.data)
            if ip not in entry.addresses:
                entry.addresses.append(ip)


def _to_projectors(responders: dict[str, MDNSResult]) -> list[Projector]:
    out: list[Projector] = []
    for source, info in responders.items():
        if not _looks_like_projector(info):
            continue
        host = info.addresses[0] if info.addresses else source
        name = info.txt.get("n") or info.txt.get("fn") or info.txt.get("name")
        out.append(
            Projector(
                host=host,
                port=info.port or 4352,
                protocol=Protocol.UNKNOWN,
                name=name,
                extras={
                    "mdns_services": info.services,
                    "mdns_txt": info.txt,
                    "mdns_names": info.names,
                },
            )
        )
    return out


_PROJECTOR_HINTS = ("epson", "projector", "pdl", "usleep", "airplay", "raop", "beamer")


def _looks_like_projector(info: MDNSResult) -> bool:
    haystack = " ".join(
        list(info.txt.values())
        + info.services
        + info.names
    ).lower()
    return any(hint in haystack for hint in _PROJECTOR_HINTS)


__all__ = ["discover_mdns", "MDNSResult", "SERVICE_TYPES"]
