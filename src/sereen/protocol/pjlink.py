"""PJLink protocol implementation.

PJLink is the industry standard for projector control. It is supported by
most professional Epson models. It operates on TCP port 4352.
"""

from __future__ import annotations

import socket
import time
from typing import Any

from ..models import ProjectorState
from ..control.base import AuthError, ControlError, ProtocolError, Session


DEFAULT_PORT = 4352


class PJLinkSession(Session):
    """A live PJLink connection to a projector."""

    protocol_name = "pjlink"

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        password: str | None = None,
        timeout: float = 3.0,
    ) -> None:
        super().__init__(host, port, timeout)
        self.password = password
        self._sock: socket.socket | None = None
        self._authenticated = False

    def connect(self) -> None:
        try:
            self._sock = socket.create_connection((self.host, self.port), self.timeout)
            self._sock.settimeout(self.timeout)
        except OSError as exc:
            raise ControlError(f"cannot reach {self.host}:{self.port}: {exc}") from exc

        # PJLink requires a Power query to verify connection
        try:
            # PJLink commands are usually: #1PWR=1\r
            # We send a simple query to check if it's alive
            self._send("#1PWR=?")
        except AuthError:
            raise
        except ControlError:
            self.close()
            raise

        self._authenticated = True

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _send(self, command: str) -> str:
        """Send a raw PJLink command and return the response."""
        if self._sock is None:
            raise ControlError("not connected")

        # PJLink commands must end with \r
        payload = f"{command}\r".encode("ascii")
        try:
            self._sock.sendall(payload)
        except OSError as exc:
            raise ControlError(f"send failed: {exc}") from exc

        return self._read_response()

    def _read_response(self) -> str:
        """Read PJLink response. PJLink responses are usually short."""
        try:
            data = self._sock.recv(1024)
            if not data:
                return ""
            return data.decode("ascii", "replace").strip()
        except socket.timeout:
            return ""
        except OSError as exc:
            raise ControlError(f"read failed: {exc}") from exc

    def info(self) -> dict[str, Any]:
        """Retrieve projector info using PJLink queries."""
        info: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol_name,
        }

        # PJLink model query: #1MOD=?
        model = self._query("MOD")
        if model:
            info["model"] = model

        return info

    def _query(self, key: str) -> str | None:
        """Helper to send a PJLink query and return the result."""
        answer = self._send(f"#1{key}=?")
        if not answer or "ERR" in answer:
            return None
        # PJLink answers often look like: #1MOD=Epson EB-X41
        if "=" in answer:
            return answer.split("=", 1)[1].strip()
        return answer.strip() or None

    def state(self) -> ProjectorState:
        state = ProjectorState()
        power = self._query("PWR")
        if power is not None:
            # PJLink Power: 1 = On, 0 = Off, 2 = Warming up, 3 = Cooling down
            state.power = power in ("1", "2")

        return state

    # Overriding base methods because PJLink uses different command strings
    def power_on(self) -> None:
        self._send("#1PWR=1")

    def power_off(self) -> None:
        self._send("#1PWR=0")

    def set_input(self, source: str) -> None:
        # PJLink source: #1INPUT=1
        # Note: mapping source name to index is model-dependent
        self._send(f"#1INPUT={source}")
