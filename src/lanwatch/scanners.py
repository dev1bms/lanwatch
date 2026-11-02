from __future__ import annotations

import errno
import logging
import socket
import time
from collections.abc import Iterator
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any, Protocol

from .config import ScanMethod, Settings
from .models import Found, Notice
from .network import NetworkInfo

log = logging.getLogger(__name__)

_ATF_COM = 0x02
_DISCARD_PORT = 9


class ScanError(RuntimeError):
    pass


class ScanPermissionError(ScanError):
    pass


class Scanner(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def notices(self) -> tuple[Notice, ...]: ...

    def scan(self) -> list[Found]: ...


def normalize_mac(mac: str) -> str:
    return mac.strip().lower().replace("-", ":")


def _require_subnets(network: NetworkInfo) -> None:
    if not network.subnets:
        raise ScanError("no subnet to scan; set LW_INTERFACE or LW_SUBNETS")


def _round_trip_ms(sent: Any, received: Any) -> float | None:
    if not sent.sent_time:
        return None
    return round(max(float(received.time) - float(sent.sent_time), 0.0) * 1000, 2)


class ArpScanner:
    name = "arp"
    notices: tuple[Notice, ...] = ()

    def __init__(self, network: NetworkInfo, *, timeout: float = 2.0, retry: int = 2) -> None:
        self._network = network
        self._timeout = timeout
        self._retry = retry

    def scan(self) -> list[Found]:
        _require_subnets(self._network)
        from scapy.config import conf
        from scapy.layers.l2 import ARP, Ether
        from scapy.sendrecv import srp

        conf.verb = 0
        found: dict[str, Found] = {}
        for net in self._network.subnets:
            try:
                answered, _ = srp(
                    Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=str(net)),
                    iface=self._network.interface,
                    timeout=self._timeout,
                    retry=self._retry,
                    verbose=False,
                )
            except OSError as exc:
                if isinstance(exc, PermissionError) or exc.errno in (errno.EPERM, errno.EACCES):
                    raise ScanPermissionError("ARP scanning needs root or CAP_NET_RAW") from exc
                raise
            for sent, received in answered:
                if IPv4Address(received.psrc) not in net:
                    continue
                mac = normalize_mac(received.hwsrc)
                found.setdefault(mac, Found(ip=received.psrc, mac=mac, rtt_ms=_round_trip_ms(sent, received)))
        return list(found.values())


class NeighborScanner:
    name = "neigh"
    notices: tuple[Notice, ...] = ()

    def __init__(self, network: NetworkInfo, *, settle: float = 2.0, table: Path = Path("/proc/net/arp")) -> None:
        self._network = network
        self._settle = settle
        self._table = table

    def scan(self) -> list[Found]:
        _require_subnets(self._network)
        targets = list(self._hosts())
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setblocking(False)
            for _ in range(2):
                for ip in targets:
                    try:
                        sock.sendto(b"", (ip, _DISCARD_PORT))
                    except OSError:
                        continue
                time.sleep(self._settle / 2)
        return self.read_table()

    def read_table(self) -> list[Found]:
        try:
            lines = self._table.read_text().splitlines()[1:]
        except OSError:
            return []
        found: dict[str, Found] = {}
        for line in lines:
            parts = line.split()
            if len(parts) < 6:
                continue
            ip, flags, mac = parts[0], parts[2], normalize_mac(parts[3])
            try:
                complete = int(flags, 16) & _ATF_COM
            except ValueError:
                continue
            if complete and mac != "00:00:00:00:00:00" and self._network.contains(ip):
                found.setdefault(mac, Found(ip=ip, mac=mac))
        return list(found.values())

    def _hosts(self) -> Iterator[str]:
        for net in self._network.subnets:
            for host in net.hosts():
                yield str(host)


class AutoScanner:
    def __init__(self, primary: Scanner, fallback: Scanner) -> None:
        self._primary = primary
        self._fallback = fallback
        self._degraded = False

    @property
    def name(self) -> str:
        return self._fallback.name if self._degraded else self._primary.name

    @property
    def notices(self) -> tuple[Notice, ...]:
        return (Notice("arp_no_permission"),) if self._degraded else ()

    def scan(self) -> list[Found]:
        if not self._degraded:
            try:
                return self._primary.scan()
            except ScanPermissionError:
                self._degraded = True
                log.warning("raw sockets are not permitted, falling back to the kernel neighbour table")
        return self._fallback.scan()


def build_scanner(settings: Settings, network: NetworkInfo) -> Scanner:
    arp = ArpScanner(network, timeout=settings.arp_timeout, retry=settings.arp_retry)
    neighbor = NeighborScanner(network)
    match settings.scan_method:
        case ScanMethod.ARP:
            return arp
        case ScanMethod.NEIGH:
            return neighbor
        case _:
            return AutoScanner(arp, neighbor)
