"""Tests for configuration handling."""

from __future__ import annotations

import json

import pytest

from sereen import config
from sereen.models import Projector, Protocol


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("SEREEN_CONFIG_DIR", str(tmp_path / "cfg"))
    return tmp_path


def test_config_roundtrip():
    cfg = config.Config()
    cfg.remember(Projector(host="192.168.1.7", name="Hall", protocol=Protocol.PJLINK))
    assert config.Config.load().saved[0].host == "192.168.1.7"


def test_remember_updates_existing_entry():
    cfg = config.Config()
    cfg.remember(Projector(host="192.168.1.7", name="Hall"))
    cfg.remember(Projector(host="192.168.1.7", name="Hall 2", protocol=Protocol.PJLINK))
    assert len(cfg.saved) == 1
    assert cfg.saved[0].name == "Hall 2"
    assert cfg.saved[0].protocol is Protocol.PJLINK


def test_forget():
    cfg = config.Config()
    cfg.remember(Projector(host="192.168.1.7"))
    assert cfg.forget("192.168.1.7") is True
    assert cfg.forget("192.168.1.7") is False
    assert not cfg.saved


def test_secrets_roundtrip():
    config.save_secret("192.168.1.7", "hunter2")
    assert config.get_secret("192.168.1.7") == "hunter2"
    assert config.delete_secret("192.168.1.7") is True
    assert config.get_secret("192.168.1.7") is None


def test_config_file_is_valid_json():
    cfg = config.Config()
    cfg.remember(Projector(host="192.168.1.7"))
    raw = json.loads(config.config_path().read_text(encoding="utf-8"))
    assert raw["saved"][0]["host"] == "192.168.1.7"


def test_load_tolerates_corrupt_file():
    config.config_path().parent.mkdir(parents=True, exist_ok=True)
    config.config_path().write_text("{ not json", encoding="utf-8")
    assert config.Config.load().saved == []
