"""sereen - discover and control Epson projectors from Linux.

The package is layered:

``sereen.discovery``
    Find projectors on the local network (TCP sweep, Epson SDP, SSDP, mDNS).
``sereen.protocol``
    Wire codecs: PJLink and ESC/VP.net.
``sereen.control``
    High-level session objects that turn protocol bytes into commands.
``sereen.cli``
    The ``sereen`` command line interface.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .models import Connection, Projector, ProjectorState, Protocol

__all__ = [
    "__version__",
    "Projector",
    "ProjectorState",
    "Protocol",
    "Connection",
]
