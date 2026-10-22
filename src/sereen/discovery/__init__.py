"""Discovery layer: find projectors on the local network.

Three independent strategies, because different projector models expose
different things:

* :func:`scan_network` - TCP connect sweep over the local subnets.  Works
  for anything with an open control port, needs no cooperation from the
  projector.
* :func:`discover_sdp` - Epson's own UDP broadcast probe.
* :func:`discover_ssdp` / :func:`discover_mdns` - UPnP and DNS-SD.

Run them all and merge the results.
"""

from __future__ import annotations

from ..models import Projector
from .mdns import discover_mdns
from .scan import DEFAULT_PORTS, ScanOptions, scan_hosts, scan_network
from .sdp import discover_sdp
from .ssdp import discover_ssdp

__all__ = [
    "ScanOptions",
    "DEFAULT_PORTS",
    "scan_network",
    "scan_hosts",
    "discover_sdp",
    "discover_ssdp",
    "discover_mdns",
    "discover_all",
]


def discover_all(
    options: ScanOptions | None = None, use_broadcast: bool = True
) -> list[Projector]:
    """Run every discovery strategy and merge the results.

    Duplicate hosts are collapsed; the first protocol seen for a host wins,
    with PJLink preferred because it is the richest and best documented.
    """
    opts = options or ScanOptions()
    found: dict[str, Projector] = {}

    def add(projector: Projector) -> None:
        existing = found.get(projector.host)
        if existing is None:
            found[projector.host] = projector
            return
        # Merge: keep the most specific protocol and the best name we have.
        if existing.protocol == Projector.protocol.UNKNOWN:
            existing.protocol = projector.protocol
            existing.port = projector.port
        existing.name = existing.name or projector.name
        existing.model = existing.model or projector.model
        existing.manufacturer = existing.manufacturer or projector.manufacturer
        existing.extras.update(projector.extras)

    if use_broadcast:
        for projector in discover_sdp(timeout=opts.timeout):
            add(projector)
        for projector in discover_ssdp(timeout=opts.timeout):
            add(projector)
        for projector in discover_mdns(timeout=opts.timeout):
            add(projector)

    for projector in scan_network(opts):
        add(projector)

    return sorted(found.values(), key=lambda p: p.host)
