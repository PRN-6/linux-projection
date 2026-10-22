"""Control layer: open a session with a projector.

The entry point is :func:`open_session`, which tries the supported protocols
in order and returns the first one that answers.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..models import Protocol
from .base import AuthError, ControlError, ProtocolError, Session

__all__ = [
    "Session",
    "ControlError",
    "AuthError",
    "ProtocolError",
    "open_session",
    "PROTOCOL_ORDER",
]

#: Protocols to try, most capable first.  PJLink is the cross-vendor standard
#: and gives the richest state readout; ESC/VP.net is the Epson fallback.
PROTOCOL_ORDER: tuple[Protocol, ...] = (
    Protocol.PJLINK,
    Protocol.ESCVP,
    Protocol.ESCVP21,
)

#: Default TCP port per protocol.
DEFAULT_PORTS: dict[Protocol, int] = {
    Protocol.PJLINK: 4352,
    Protocol.ESCVP: 3620,
    Protocol.ESCVP21: 3621,
}


def _make_session(
    protocol: Protocol, host: str, port: int, password: str | None, timeout: float
) -> Session:
    from ..protocol import escvp, pjlink

    if protocol is Protocol.PJLINK:
        return pjlink.PJLinkSession(host, port, password=password, timeout=timeout)
    if protocol in (Protocol.ESCVP, Protocol.ESCVP21):
        return escvp.ESCVPSession(
            host, port, password=password, timeout=timeout, variant=protocol
        )
    raise ControlError(f"unsupported protocol: {protocol}")


def open_session(
    host: str,
    port: int | None = None,
    password: str | None = None,
    protocol: Protocol | None = None,
    timeout: float = 3.0,
    prefer: Sequence[Protocol] = PROTOCOL_ORDER,
) -> Session:
    """Connect to a projector and return a usable session.

    When ``protocol`` is given, only that protocol is tried.  Otherwise the
    protocols in ``prefer`` are tried in order, and the first one that
    successfully identifies the projector wins.

    Raises :class:`ControlError` if no protocol answers.
    """
    order = (protocol,) if protocol is not None else tuple(prefer)
    errors: list[str] = []

    for proto in order:
        target_port = port if port is not None else DEFAULT_PORTS.get(proto, 4352)
        session = _make_session(proto, host, target_port, password, timeout)
        try:
            session.connect()  # type: ignore[attr-defined]
        except ControlError as exc:
            errors.append(f"{proto}: {exc}")
            session.close()
            continue
        return session

    detail = "; ".join(errors) if errors else "no protocols attempted"
    raise ControlError(f"could not connect to {host} ({detail})")
