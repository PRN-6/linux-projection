"""Helpers for working with the local network layout.

Pure stdlib.  When ``psutil`` is installed we use it (it knows the netmask on
every platform); otherwise we fall back to parsing ``/proc/net/route`` on
Linux and finally to assuming a /24 for every local address.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable, Iterator

try:  # optional dependency
    import psutil  # type: ignore
except Exception:  # pragma: no cover - depends on environment
    psutil = None  # type: ignore


def _iter_psutil_networks() -> Iterator[ipaddress.IPv4Network]:
    if psutil is None:
        return
    for addrs in psutil.net_if_addrs().values():
        for addr in addrs:
            if addr.family != socket.AF_INET or addr.netmask is None:
                continue
            try:
                net = ipaddress.ip_network(
                    f"{addr.address}/{addr.netmask}", strict=False
                )
            except ValueError:
                continue
            yield net


def _iter_proc_net_networks() -> Iterator[ipaddress.IPv4Network]:
    """Derive subnets from the Linux kernel routing table.

    ``/proc/net/route`` gives each interface's netmask directly; we pair it
    with the interface address obtained from ``/proc/net/fib_trie``-free
    ``getaddrinfo`` probing of the interface name.
    """
    try:
        with open("/proc/net/route", encoding="utf-8") as fh:
            lines = fh.read().splitlines()[1:]
    except OSError:
        return

    for line in lines:
        fields = line.split()
        if len(fields) < 8:
            continue
        iface, netmask_hex = fields[0], fields[7]
        try:
            netmask = str(ipaddress.IPv4Address(int(netmask_hex, 16)))
        except ValueError:
            continue
        for addr in _interface_addresses(iface):
            try:
                yield ipaddress.ip_network(f"{addr}/{netmask}", strict=False)
            except ValueError:
                continue


def _interface_addresses(iface: str) -> list[str]:
    """Best-effort IPv4 address lookup for a named interface."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Not a real packet; binding selects the outgoing interface.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, iface.encode() + b"\0")
        sock.connect(("192.0.2.1", 9))  # TEST-NET-1, unrouted
        return [sock.getsockname()[0]]
    except OSError:
        return []
    finally:
        sock.close()


def _iter_hostname_networks() -> Iterator[ipaddress.IPv4Network]:
    try:
        _hostname, _aliases, addresses = socket.gethostbyname_ex(socket.gethostname())
    except OSError:
        return
    for addr in addresses:
        try:
            yield ipaddress.ip_network(f"{addr}/24", strict=False)
        except ValueError:
            continue


def local_networks() -> list[ipaddress.IPv4Network]:
    """Return the IPv4 networks of every local interface, de-duplicated."""
    nets: list[ipaddress.IPv4Network] = []
    seen: set[str] = set()
    for source in (_iter_psutil_networks, _iter_proc_net_networks, _iter_hostname_networks):
        for net in source():
            key = str(net)
            if key not in seen:
                seen.add(key)
                nets.append(net)
    return nets


def _iter_host_addresses() -> Iterator[str]:
    if psutil is not None:
        for addrs in psutil.net_if_addrs().values():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    yield addr.address
        return
    try:
        for net in _iter_proc_net_networks():
            yield str(net.network_address + 1)
    except Exception:  # pragma: no cover - defensive
        pass
    for addr in _iter_hostname_networks():
        yield str(addr.network_address + 1)


#: Networks that can never contain a projector we want to talk to.
_SKIP_NETS = (
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
)


def candidate_hosts(limit: int = 0, max_hosts: int = 65536) -> list[str]:
    """Return every plausible address of a device on the local network.

    This is the address set used by the TCP connect scan.  We include every
    host address of every local subnet; a projector on a different subnet but
    reachable by routing is not covered (use ``--host`` for that).

    Loopback and link-local networks are skipped - scanning 16k addresses on
    a ``169.254.0.0/16`` adapter finds nothing but costs a full sweep.
    """
    hosts: list[str] = []
    seen: set[str] = set()
    for net in local_networks():
        if net.prefixlen >= 31:
            continue
        if any(net.subnet_of(skip) or net.overlaps(skip) for skip in _SKIP_NETS):
            continue
        if net.is_multicast or net.is_reserved:
            continue
        for host in net.hosts():
            ip = str(host)
            if ip in seen:
                continue
            seen.add(ip)
            hosts.append(ip)
            if limit and len(hosts) >= limit:
                return hosts
            if len(hosts) >= max_hosts:
                return hosts
    return hosts


def is_private(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def resolve(host: str) -> str | None:
    """Resolve a hostname to an IPv4 address, or None."""
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


def sort_hosts(hosts: Iterable[str]) -> list[str]:
    """Sort addresses numerically where possible, lexicographically otherwise."""

    def key(host: str) -> tuple[int, int | str]:
        try:
            addr = ipaddress.ip_address(host)
            return (0, int(addr))
        except ValueError:
            return (1, host)

    return sorted(hosts, key=key)
