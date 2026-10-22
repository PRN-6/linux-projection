"""Tests for network helpers."""

from __future__ import annotations

import ipaddress

import pytest

from sereen import netutil


def test_local_networks_are_ipv4():
    for net in netutil.local_networks():
        assert isinstance(net, ipaddress.IPv4Network)


def test_candidate_hosts_skips_loopback_and_link_local():
    hosts = netutil.candidate_hosts()
    for host in hosts:
        addr = ipaddress.ip_address(host)
        assert not addr.is_loopback
        assert not addr.is_link_local


def test_candidate_hosts_respects_limit():
    assert len(netutil.candidate_hosts(limit=5)) <= 5


def test_candidate_hosts_respects_max_hosts():
    assert len(netutil.candidate_hosts(max_hosts=3)) <= 3


def test_sort_hosts_is_numeric():
    hosts = ["10.0.0.10", "10.0.0.2", "10.0.0.1", "host.local"]
    assert netutil.sort_hosts(hosts) == [
        "10.0.0.1",
        "10.0.0.2",
        "10.0.0.10",
        "host.local",
    ]


def test_is_private():
    assert netutil.is_private("192.168.1.10")
    assert netutil.is_private("10.0.0.1")
    assert not netutil.is_private("8.8.8.8")
    assert not netutil.is_private("not-an-ip")
