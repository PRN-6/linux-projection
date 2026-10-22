"""Epson ESC/VP.net protocol.

ESC/VP.net is Epson's own control protocol.  The classic variant is a
line-oriented text protocol on TCP port 3620: a request is ``KEY=VALUE``
terminated by CR LF, and the projector answers with either the same
``KEY=VALUE`` form or an ``ERR=xx`` error.

    >>> send("PWR=1")       # power on
    'PWR=1'
    >>> send("PWR=?")
    'PWR=1'

The protocol is generous: unknown commands are answered with ``ERR=xx``
rather than by dropping the connection, so a mis-typed key is safe.

Newer firmware also serves ESC/VP 21 on port 3621 and the "HDCP" screen
service on port 8889; this module speaks the text protocol against either.
"""

from __future__ import annotations

import socket
import time
from typing import Any

from ..models import ProjectorState, Protocol
from ..control.base import AuthError, ControlError, ProtocolError, Session

#: ESC/VP.net port for the classic control service.
DEFAULT_PORT = 3620
#: ESC/VP.net port for the extended (ESC/VP 21) service.
EXTENDED_PORT = 3621

#: Error codes the projector may return.
ERR_OK = "00"
ERR_UNSPECIFIED = "01"
ERR_ILLEGAL_COMMAND = "02"
ERR_BUSY = "03"
ERR_AUTHENTICATION = "04"
ERR_PARAMETER = "05"

#: Friendly input names to ESC/VP input codes.  Epson's codes differ between
#: model families, so the table is a best-effort default that can be
#: overridden from the projector's own ``INP=?`` answer.
INPUT_CODES: dict[str, str] = {
    "computer": "11",
    "vga": "11",
    "rgb": "11",
    "hdmi1": "21",
    "hdmi2": "22",
    "hdmi3": "23",
    "displayport": "31",
    "video": "12",
    "composite": "12",
    "component": "13",
    "wireless": "41",
}


class ESCVPSession(Session):
    """A live ESC/VP.net connection to a projector."""

    protocol_name = "escvp"

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        password: str | None = None,
        timeout: float = 3.0,
        variant: Protocol = Protocol.ESCVP,
    ) -> None:
        super().__init__(host, port, timeout)
        self.password = password
        self.variant = variant
        self._sock: socket.socket | None = None
        self._buffer = b""
        self._authenticated = False
        self._model: str | None = None
        self._name: str | None = None

    # ------------------------------------------------------------ socket
    def connect(self) -> None:
        try:
            self._sock = socket.create_connection((self.host, self.port), self.timeout)
            self._sock.settimeout(self.timeout)
        except OSError as exc:
            raise ControlError(f"cannot reach {self.host}:{self.port}: {exc}") from exc

        # A query is the cheapest way to find out whether we can talk to this
        # device and whether it wants a password.
        try:
            answer = self._send("PWR=?")
        except AuthError:
            raise
        except ControlError:
            self.close()
            raise

        if answer.startswith("ERR="):
            code = answer[4:].strip()
            if code in (ERR_AUTHENTICATION, ERR_BUSY):
                raise AuthError(
                    f"{self.host} rejected the connection (ERR={code}); "
                    "a network password is probably required"
                )
            raise ProtocolError(f"{self.host} answered ERR={code} to PWR=?")

        self._authenticated = True

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:  # pragma: no cover - defensive
                pass
            self._sock = None

    # ------------------------------------------------------------- wire
    def _send(self, command: str) -> str:
        """Send a raw ESC/VP command and return the raw response line."""
        if self._sock is None:
            raise ControlError("not connected")
        payload = f"{command}\r\n".encode("ascii")
        try:
            self._sock.sendall(payload)
        except OSError as exc:
            raise ControlError(f"send failed: {exc}") from exc
        return self._read_line()

    def _read_line(self) -> str:
        """Read one CRLF-terminated response line."""
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                chunk = self._sock.recv(4096)  # type: ignore[union-attr]
            except socket.timeout:
                break
            except OSError as exc:
                raise ControlError(f"read failed: {exc}") from exc
            if not chunk:
                break
            self._buffer += chunk
            if b"\n" in self._buffer:
                line, _, rest = self._buffer.partition(b"\n")
                self._buffer = rest
                return line.decode("ascii", "replace").strip()
        if self._buffer:
            line, self._buffer = self._buffer, b""
            return line.decode("ascii", "replace").strip()
        return ""

    # --------------------------------------------------------- commands
    def _query(self, key: str) -> str | None:
        answer = self._send(f"{key}=?")
        if answer.startswith("ERR="):
            return None
        if "=" in answer:
            return answer.split("=", 1)[1].strip()
        return answer.strip() or None

    def power_on(self) -> None:
        self._send("PWR=1")

    def power_off(self) -> None:
        self._send("PWR=0")

    def set_input(self, source: str) -> None:
        code = INPUT_CODES.get(source.lower(), source)
        self._send(f"INP={code}")

    def set_volume(self, level: int) -> None:
        if not 0 <= level <= 100:
            raise ValueError("volume must be between 0 and 100")
        self._send(f"VOL={level}")

    def set_mute(self, muted: bool) -> None:
        self._send(f"AMT={1 if muted else 0}")

    def info(self) -> dict[str, Any]:
        """Read whatever identity the projector is willing to give."""
        info: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol_name,
        }
        name = self._query("NAME")
        if name:
            self._name = name
            info["name"] = name
        model = self._query("MODL")
        if model:
            self._model = model
            info["model"] = model
        manufacturer = self._query("MFG")
        if manufacturer:
            info["manufacturer"] = manufacturer
        if "manufacturer" not in info:
            info["manufacturer"] = "Epson"
        inputs = self._query("INP")
        if inputs:
            info["inputs"] = inputs
        return info

    def state(self) -> ProjectorState:
        state = ProjectorState()
        power = self._query("PWR")
        if power is not None:
            state.power = power in ("1", "ON", "on", "P", "p")
        volume = self._query("VOL")
        if volume is not None and volume.isdigit():
            state.volume = int(volume)
        mute = self._query("AMT")
        if mute is not None:
            state.muted = mute in ("1", "ON", "on")
        source = self._query("INP")
        if source:
            state.input_source = source
        return state
