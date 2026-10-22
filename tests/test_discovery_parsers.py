"""Tests for the discovery parsers (mDNS, SSDP, SDP)."""

from __future__ import annotations

import socket
import struct

import pytest

from sereen.discovery.mdns import (
    _decode_name,
    _encode_name,
    _parse_message,
    _parse_txt,
)
from sereen.discovery.sdp import _parse_sdp
from sereen.discovery.ssdp import _parse_ssdp


# ------------------------------------------------------------------- mDNS
def test_encode_decode_name_roundtrip():
    name = "_pdl-datastream._tcp.local"
    encoded = _encode_name(name)
    decoded, offset = _decode_name(encoded, 0)
    assert decoded == name
    assert offset == len(encoded)


def test_decode_name_handles_compression():
    # A name at offset 12 ("foo"), then a pointer at offset 17 back to it.
    packet = bytearray()
    packet += b"\x00" * 12  # header
    packet += bytes([3]) + b"foo" + bytes([0])  # name at offset 12
    pointer_offset = len(packet)  # 17
    packet += bytes([0xC0, 12])  # pointer -> offset 12
    decoded, _ = _decode_name(bytes(packet), pointer_offset)
    assert decoded == "foo"


def test_parse_message_reads_answers():
    header = struct.pack("!6H", 0, 0x8400, 0, 1, 0, 0)
    answer = _encode_name("host.local") + struct.pack("!HHIH", 1, 0x8001, 120, 4)
    answer += socket.inet_aton("192.168.1.42")
    resources = _parse_message(header + answer)
    a_records = [r for r in resources if r.rtype == 1]
    assert len(a_records) == 1
    assert socket.inet_ntoa(a_records[0].data) == "192.168.1.42"


def test_parse_txt_record():
    rdata = b"\x0cmodel=EB-X41\x0bname=Room 1\x00"
    assert _parse_txt(rdata) == {"model": "EB-X41", "name": "Room 1"}


def test_parse_txt_handles_valueless_keys():
    assert _parse_txt(b"\x04void\x00") == {"void": ""}


# ------------------------------------------------------------------- SSDP
def test_parse_ssdp_finds_projector():
    payload = (
        "HTTP/1.1 200 OK\r\n"
        "CACHE-CONTROL: max-age=1800\r\n"
        "SERVER: Epson/1.0 UPnP/1.0 Projector/1.0\r\n"
        "USN: uuid:easyepson-1234::upnp:rootdevice\r\n"
        "LOCATION: http://192.168.1.42:8080/desc.xml\r\n"
        "\r\n"
    ).encode()
    projector = _parse_ssdp(payload, "192.168.1.42")
    assert projector is not None
    assert projector.host == "192.168.1.42"


def test_parse_ssdp_ignores_unrelated_devices():
    payload = (
        "HTTP/1.1 200 OK\r\n"
        "SERVER: Linux/5.0 UPnP/1.0 MiniUPnPd/2.x\r\n"
        "USN: uuid:printer::upnp:rootdevice\r\n"
        "\r\n"
    ).encode()
    assert _parse_ssdp(payload, "192.168.1.9") is None


# -------------------------------------------------------------------- SDP
def test_parse_sdp_extracts_model():
    data = b"\x00\x00EPSON\x00EB-X41\x00Room 1\x00" + b"\x00\x11\x22\x33\x44\x55"
    projector = _parse_sdp(data, "192.168.1.42")
    assert projector is not None
    assert projector.host == "192.168.1.42"
    assert projector.manufacturer == "Epson"
    assert "00:11:22:33:44:55" in projector.extras["mac_addresses"]


def test_parse_sdp_ignores_empty():
    assert _parse_sdp(b"", "192.168.1.42") is None
