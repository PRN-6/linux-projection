"""Persistent configuration: saved projectors, credentials, preferences.

Stored as JSON under ``$XDG_CONFIG_HOME/sereen/config.json`` (or the platform
equivalent).  Passwords are kept in a separate file with restrictive
permissions so that a casual ``cat`` of the config does not leak them.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import Projector, Protocol

APP_NAME = "sereen"


def config_dir() -> Path:
    override = os.environ.get("SEREEN_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


def secrets_path() -> Path:
    return config_dir() / "secrets.json"


@dataclass
class SavedProjector:
    """A projector the user has connected to before."""

    host: str
    name: str | None = None
    protocol: Protocol = Protocol.UNKNOWN
    port: int = 4352
    #: Protocol used for the last successful session, e.g. "pjlink".
    last_protocol: str | None = None
    notes: str | None = None

    def to_projector(self) -> Projector:
        return Projector(
            host=self.host,
            port=self.port,
            protocol=self.protocol,
            name=self.name,
        )


@dataclass
class Config:
    saved: list[SavedProjector] = field(default_factory=list)
    #: Default timeout for network operations, in seconds.
    timeout: float = 3.0
    #: Extra hosts to always probe, outside the local subnets.
    extra_hosts: list[str] = field(default_factory=list)
    #: Reuse the last used protocol for a saved host before probing others.
    prefer_saved_protocol: bool = True

    # ------------------------------------------------------------------ io
    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls.from_dict(raw)

    def save(self) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _restrict(path)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Config":
        saved = []
        for item in raw.get("saved", []) or []:
            try:
                saved.append(
                    SavedProjector(
                        host=str(item["host"]),
                        name=item.get("name"),
                        protocol=Protocol(item.get("protocol", "unknown")),
                        port=int(item.get("port", 4352)),
                        last_protocol=item.get("last_protocol"),
                        notes=item.get("notes"),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return cls(
            saved=saved,
            timeout=float(raw.get("timeout", 3.0)),
            extra_hosts=[str(h) for h in raw.get("extra_hosts", []) or []],
            prefer_saved_protocol=bool(raw.get("prefer_saved_protocol", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "saved": [
                {
                    "host": s.host,
                    "name": s.name,
                    "protocol": s.protocol.value,
                    "port": s.port,
                    "last_protocol": s.last_protocol,
                    "notes": s.notes,
                }
                for s in self.saved
            ],
            "timeout": self.timeout,
            "extra_hosts": self.extra_hosts,
            "prefer_saved_protocol": self.prefer_saved_protocol,
        }

    # ------------------------------------------------------------- mutate
    def remember(self, projector: Projector) -> SavedProjector:
        """Add or update the entry for ``projector`` and persist."""
        for entry in self.saved:
            if entry.host == projector.host:
                entry.name = projector.name or entry.name
                entry.protocol = projector.protocol
                entry.port = projector.port
                entry.last_protocol = projector.protocol.value
                self.save()
                return entry
        entry = SavedProjector(
            host=projector.host,
            name=projector.name,
            protocol=projector.protocol,
            port=projector.port,
            last_protocol=projector.protocol.value,
        )
        self.saved.append(entry)
        self.save()
        return entry

    def forget(self, host: str) -> bool:
        before = len(self.saved)
        self.saved = [s for s in self.saved if s.host != host]
        if len(self.saved) != before:
            self.save()
            return True
        return False


# ------------------------------------------------------------------ secrets
def _restrict(path: Path) -> None:
    """Best-effort chmod 0600 - the file holds projector passwords."""
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:  # pragma: no cover - unsupported on some filesystems
        pass


def load_secrets() -> dict[str, str]:
    path = secrets_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


def save_secret(host: str, password: str) -> None:
    path = secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    secrets = load_secrets()
    secrets[host] = password
    path.write_text(json.dumps(secrets, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _restrict(path)


def get_secret(host: str) -> str | None:
    return load_secrets().get(host)


def delete_secret(host: str) -> bool:
    path = secrets_path()
    if not path.exists():
        return False
    secrets = load_secrets()
    if host not in secrets:
        return False
    del secrets[host]
    path.write_text(json.dumps(secrets, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _restrict(path)
    return True
