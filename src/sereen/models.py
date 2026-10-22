"""Core data types shared by discovery, protocol and control layers."""

from __future__ import annotations

import dataclasses
import enum
import ipaddress
from dataclasses import dataclass, field
from typing import Any


class Protocol(str, enum.Enum):
    """Wire protocol a projector was found on."""

    PJLINK = "pjlink"
    ESCVP = "escvp"
    ESCVP21 = "escvp21"
    UNKNOWN = "unknown"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class Connection(enum.Enum):
    """How the projector was reached (not how it renders)."""

    WIRED = "wired"
    WIRELESS = "wireless"
    UNKNOWN = "unknown"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


@dataclass
class Projector:
    """A projector discovered on the local network.

    Instances are created by the discovery layer and later enriched with
    information read back from the device (model name, power state, ...).
    """

    host: str
    port: int = 4352
    protocol: Protocol = Protocol.UNKNOWN
    name: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    connection: Connection = Connection.UNKNOWN
    #: Free-form extras (mDNS TXT records, SSDP headers, ...).
    extras: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.host = str(self.host)
        # Keep the address canonical so that 192.168.1.7 == 192.168.1.007.
        try:
            self.host = str(ipaddress.ip_address(self.host))
        except ValueError:
            pass  # hostname, keep as-is

    @property
    def display_name(self) -> str:
        return self.name or self.model or self.host

    @property
    def is_known_protocol(self) -> bool:
        return self.protocol in (Protocol.PJLINK, Protocol.ESCVP, Protocol.ESCVP21)

    def to_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data["protocol"] = self.protocol.value
        data["connection"] = self.connection.value
        return data

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.display_name} ({self.host}:{self.port} {self.protocol})"


@dataclass
class ProjectorState:
    """Snapshot of a projector's current state."""

    power: bool | None = None
    input_source: str | None = None
    volume: int | None = None
    muted: bool | None = None
    lamp_hours: int | None = None
    temperature: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)
