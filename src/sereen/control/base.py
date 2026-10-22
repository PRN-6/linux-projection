"""High-level session objects.

A *session* is a live connection to one projector.  It hides the differences
between PJLink and ESC/VP.net behind a small, uniform API:

    with open_session("192.168.1.7") as s:
        s.power_on()
        s.set_input("hdmi1")
"""

from __future__ import annotations

import abc
from typing import Any

from ..models import ProjectorState


class ControlError(Exception):
    """Raised when a projector rejects or fails to answer a command."""


class AuthError(ControlError):
    """Raised when the projector requires a password we do not have."""


class ProtocolError(ControlError):
    """Raised when the answer cannot be parsed."""


class Session(abc.ABC):
    """Base class for a connection to a projector."""

    #: Human readable name of the protocol, used in messages.
    protocol_name = "unknown"

    def __init__(self, host: str, port: int, timeout: float = 3.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    # -- to be implemented by concrete protocols -----------------------
    @abc.abstractmethod
    def connect(self) -> None:
        """Open the connection and identify the device.

        Raises :class:`ControlError` if the projector does not answer or the
        credentials are rejected.
        """

    @abc.abstractmethod
    def _send(self, command: str) -> str:
        """Send a raw command and return the raw response."""

    @abc.abstractmethod
    def info(self) -> dict[str, Any]:
        """Return device information (name, model, manufacturer, ...)."""

    @abc.abstractmethod
    def state(self) -> ProjectorState:
        """Return the current state of the projector."""

    # -- convenience wrappers around the raw command ------------------
    def power_on(self) -> None:
        self._send("PWON")

    def power_off(self) -> None:
        self._send("PWOFF")

    def set_input(self, source: str) -> None:
        self._send(f"INP:{source}")

    def set_volume(self, level: int) -> None:
        if not 0 <= level <= 100:
            raise ValueError("volume must be between 0 and 100")
        self._send(f"VOL:{level}")

    def set_mute(self, muted: bool) -> None:
        self._send(f"MUTE:{'1' if muted else '0'}")

    def close(self) -> None:
        """Release the connection.  Safe to call more than once."""

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<{type(self).__name__} {self.host}:{self.port}>"
