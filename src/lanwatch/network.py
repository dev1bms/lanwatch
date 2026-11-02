from __future__ import annotations

import fcntl
import logging
import socket
import struct
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import NamedTuple

from .models import Notice

log = logging.getLogger(__name__)

_SIOCGIFADDR = 0x8915
_SIOCGIFNETMASK = 0x891B
_RTF_UP = 0x0001

AUTO_MAX_PREFIX = 22
MIN_PREFIX = 16


class Route(NamedTuple):
    iface: str
    dest: str
    gateway: str
    flags: int
    mask: str


@dataclass(frozen=True, slots=True)
class NetworkInfo:
    interface: str | None
    subnets: tuple[IPv4Network, ...]
    gateway: str | None
    self_ip: str | None
    self_mac: str | None
    notices: tuple[Notice, ...] = field(default=())

    def contains(self, ip: str) -> bool:
        try:
            address = IPv4Address(ip)
        except ValueError:
            return False
        return any(address in net for net in self.subnets)


def hex_to_ip(value: str) -> str:
    return socket.inet_ntoa(struct.pack("<L", int(value, 16)))


def read_routes(path: Path = Path("/proc/net/route")) -> list[Route]:
    try:
        lines = path.read_text().splitlines()[1:]
    except OSError:
        return []
    routes = []
    for line in lines:
        parts = line.split()
        if len(parts) < 8:
            continue
        try:
            routes.append(
                Route(parts[0], hex_to_ip(parts[1]), hex_to_ip(parts[2]), int(parts[3], 16), hex_to_ip(parts[7]))
            )
        except ValueError:
            continue
    return routes


def default_route(routes: list[Route], iface: str | None = None) -> tuple[str | None, str | None]:
    for route in routes:
        is_default = route.dest == "0.0.0.0" and route.mask == "0.0.0.0" and route.flags & _RTF_UP
        if is_default and iface in (None, route.iface):
            return route.iface, route.gateway
    return iface, None


def interface_ipv4(iface: str) -> tuple[str, str] | None:
    request = struct.pack("256s", iface[:15].encode())
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            ip = socket.inet_ntoa(fcntl.ioctl(sock.fileno(), _SIOCGIFADDR, request)[20:24])
            mask = socket.inet_ntoa(fcntl.ioctl(sock.fileno(), _SIOCGIFNETMASK, request)[20:24])
        except OSError:
            return None
    return ip, mask


def interface_mac(iface: str) -> str | None:
    try:
        mac = Path(f"/sys/class/net/{iface}/address").read_text().strip().lower()
    except OSError:
        return None
    return mac if mac and mac != "00:00:00:00:00:00" else None


def _configured_subnets(raw: tuple[str, ...]) -> tuple[list[IPv4Network], list[Notice]]:
    nets: list[IPv4Network] = []
    notices: list[Notice] = []
    for value in raw:
        try:
            net = IPv4Network(value, strict=False)
        except ValueError:
            notices.append(Notice("subnet_invalid", {"subnet": value}))
            continue
        if net.prefixlen < MIN_PREFIX:
            notices.append(Notice("subnet_too_large", {"subnet": str(net)}))
            continue
        nets.append(net)
    return nets, notices


def detect_network(subnets: tuple[str, ...] = (), interface: str | None = None) -> NetworkInfo:
    iface, gateway = default_route(read_routes(), interface)
    self_ip = self_mac = None
    detected: IPv4Network | None = None
    if iface:
        address = interface_ipv4(iface)
        if address:
            self_ip, mask = address
            detected = IPv4Network(f"{self_ip}/{mask}", strict=False)
        self_mac = interface_mac(iface)

    nets, notices = _configured_subnets(subnets)
    if not subnets and detected is not None:
        if detected.prefixlen < AUTO_MAX_PREFIX:
            narrowed = IPv4Network(f"{self_ip}/24", strict=False)
            notices.append(Notice("net_narrowed", {"detected": str(detected), "scanned": str(narrowed)}))
            detected = narrowed
        nets.append(detected)
    if not nets:
        notices.append(Notice("net_undetected"))

    info = NetworkInfo(iface, tuple(nets), gateway, self_ip, self_mac, tuple(notices))
    log.info("network: iface=%s subnets=%s gateway=%s self=%s", iface, [str(n) for n in nets], gateway, self_ip)
    return info
