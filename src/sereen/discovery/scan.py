"""TCP connect scan across the local network.

A projector is usually identified by which TCP ports it answers on, so the
scan is a parallel connect sweep against a set of (port, protocol) pairs.
Connect-only probing is cheap: a refused connection is answered by the kernel
in microseconds on a local subnet, and a filtered port times out.

The heavier protocol identification (handshake, name query) happens *after*
the scan, only for hosts that actually answered, so a full sweep stays fast.
"""

from __future__ import annotations

import socket
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..models import Projector, Protocol

#: (port, protocol) pairs worth probing on a projector.
#:
#: 4352  - PJLink (industry standard, supported by many Epson business models)
#: 3620  - ESC/VP.net control (Epson proprietary, classic)
#: 3621  - ESC/VP.net extended service
#: 8889  - Epson network projection / HDCP service
DEFAULT_PORTS: tuple[tuple[int, Protocol], ...] = (
    (4352, Protocol.PJLINK),
    (3620, Protocol.ESCVP),
    (3621, Protocol.ESCVP21),
    (8889, Protocol.ESCVP21),
)

#: Number of concurrent connect attempts.
DEFAULT_WORKERS = 128


@dataclass
class ScanOptions:
    """Tuning knobs for :func:`scan_network`."""

    timeout: float = 1.5
    workers: int = DEFAULT_WORKERS
    ports: tuple[tuple[int, Protocol], ...] = DEFAULT_PORTS
    hosts: list[str] | None = None
    max_hosts: int = 65536


def _probe(host: str, port: int, timeout: float) -> bool:
    """Return True if a TCP connection to host:port can be established."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def scan_hosts(
    hosts: Iterable[str],
    options: ScanOptions | None = None,
    on_found: Callable[[str, int, Protocol], None] | None = None,
) -> list[Projector]:
    """Probe every host/port pair and return the projectors that answered."""
    opts = options or ScanOptions()
    targets = [(host, port, proto) for host in hosts for port, proto in opts.ports]
    if not targets:
        return []

    found: list[Projector] = []
    seen: set[tuple[str, int]] = set()

    with ThreadPoolExecutor(max_workers=opts.workers) as pool:
        futures = {
            pool.submit(_probe, host, port, opts.timeout): (host, port, proto)
            for host, port, proto in targets
        }
        for future, (host, port, proto) in futures.items():
            try:
                if not future.result():
                    continue
            except Exception:  # pragma: no cover - defensive
                continue
            if (host, port) in seen:
                continue
            seen.add((host, port))
            projector = Projector(host=host, port=port, protocol=proto)
            found.append(projector)
            if on_found is not None:
                on_found(host, port, proto)

    found.sort(key=lambda p: (p.host, p.port))
    return found


def scan_network(options: ScanOptions | None = None) -> list[Projector]:
    """Scan the local subnets and return every projector that answered."""
    from .. import netutil

    opts = options or ScanOptions()
    hosts = opts.hosts
    if hosts is None:
        hosts = netutil.candidate_hosts(max_hosts=opts.max_hosts)
    else:
        hosts = netutil.sort_hosts(hosts)
    return scan_hosts(hosts, opts)


def wait_for_port(
    host: str, port: int, timeout: float = 10.0, interval: float = 0.5
) -> bool:
    """Poll until a port accepts connections or the timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _probe(host, port, min(1.0, timeout)):
            return True
        time.sleep(interval)
    return False
