"""Session factory for creating protocol-specific connections.

This module provides the logic to bridge the gap between a discovered
Projector object and a live, controllable Session.
"""

from __future__ import annotations

from typing import Any
from . import models
from .control.base import Session, ControlError
from .protocol.escvp import ESCVPSession
from .protocol.pjlink import PJLinkSession

def open_session(
    projector: models.Projector,
    password: str | None = None,
    timeout: float = 3.0
) -> Session:
    """
    Factory function that returns a live session based on the projector's protocol.

    Args:
        projector: The discovered projector object.
        password: Optional network password.
        timeout: Connection timeout in seconds.

    Returns:
        A connected Session object (ESCVPSession or PJLinkSession).

    Raises:
        ControlError: If the protocol is unsupported or connection fails.
    """
    proto = projector.protocol

    if proto == models.Protocol.PJLINK:
        session = PJLinkSession(
            host=projector.host,
            port=projector.port,
            password=password,
            timeout=timeout
        )
    elif proto in (models.Protocol.ESCVP, models.Protocol.ESCVP21):
        session = ESCVPSession(
            host=projector.host,
            port=projector.port,
            password=password,
            timeout=timeout
        )
    else:
        raise ControlError(f"Unsupported or unknown protocol: {proto}")

    # Attempt to connect before returning
    session.connect()
    return session
