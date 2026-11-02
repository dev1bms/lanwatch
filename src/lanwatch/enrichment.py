from __future__ import annotations

import concurrent.futures as cf
import socket
import threading
import time
from collections.abc import Sequence
from functools import lru_cache

from netaddr import EUI, AddrFormatError, NotRegisteredError

from .models import DeviceType, Found, Observation
from .network import NetworkInfo

_TYPE_RULES: tuple[tuple[DeviceType, tuple[str, ...]], ...] = (
    (
        DeviceType.PRINTER,
        (
            "printer",
            "laserjet",
            "officejet",
            "deskjet",
            "epson",
            "canon",
            "brother",
            "kyocera",
            "lexmark",
            "xerox",
            "ricoh",
        ),
    ),
    (DeviceType.TV, ("tv", "bravia", "roku", "chromecast", "firestick", "hisense", "vizio", "webos", "tizen")),
    (DeviceType.CONSOLE, ("playstation", "ps4", "ps5", "xbox", "nintendo", "sony interactive")),
    (DeviceType.TABLET, ("ipad", "galaxy-tab", "galaxytab", "kindle", "fire-tablet", "mediapad")),
    (
        DeviceType.PHONE,
        (
            "iphone",
            "android",
            "galaxy",
            "pixel",
            "redmi",
            "poco",
            "oneplus",
            "realme",
            "oppo",
            "vivo",
            "motorola",
            "moto-",
        ),
    ),
    (DeviceType.SPEAKER, ("sonos", "echo", "alexa", "homepod", "google-home", "nest-audio", "nest-mini", "bose")),
    (DeviceType.CAMERA, ("camera", "ipcam", "hikvision", "dahua", "reolink", "ezviz", "wyze", "tapo-c", "doorbell")),
    (DeviceType.SERVER, ("raspberry", "server", "synology", "qnap", "proxmox", "unraid", "truenas", "homeassistant")),
    (
        DeviceType.COMPUTER,
        (
            "macbook",
            "imac",
            "mac-mini",
            "macmini",
            "laptop",
            "desktop-",
            "thinkpad",
            "lenovo",
            "dell",
            "asustek",
            "acer",
            "micro-star",
            "intel corporate",
            "hon hai",
            "liteon",
            "azurewave",
            "windows",
        ),
    ),
    (
        DeviceType.IOT,
        (
            "espressif",
            "tuya",
            "shelly",
            "sonoff",
            "itead",
            "tasmota",
            "esp_",
            "esp-",
            "signify",
            "philips lighting",
            "lifx",
            "broadlink",
            "ecobee",
            "smartthings",
            "plug",
            "bulb",
        ),
    ),
    (
        DeviceType.ROUTER,
        (
            "router",
            "gateway",
            "openwrt",
            "fritz",
            "avm gmbh",
            "mikrotik",
            "ubiquiti",
            "netgear",
            "linksys",
            "sagemcom",
            "askey",
            "mitrastar",
            "arcadyan",
            "zte",
        ),
    ),
)
_PHONE_VENDORS = ("apple", "samsung", "xiaomi", "huawei")


@lru_cache(maxsize=4096)
def vendor_for(mac: str) -> str | None:
    try:
        org: str = EUI(mac).oui.registration().org
    except (NotRegisteredError, AddrFormatError, IndexError, ValueError):
        return None
    return org.strip() or None


def is_random_mac(mac: str) -> bool:
    try:
        return bool(int(mac.split(":", maxsplit=1)[0], 16) & 0x02)
    except ValueError:
        return False


def guess_type(
    vendor: str | None,
    hostname: str | None,
    *,
    random_mac: bool = False,
    is_gateway: bool = False,
    is_self: bool = False,
) -> DeviceType:
    if is_gateway:
        return DeviceType.ROUTER
    if is_self:
        return DeviceType.SERVER
    haystack = f"{hostname or ''} {vendor or ''}".lower()
    for dev_type, keywords in _TYPE_RULES:
        if any(keyword in haystack for keyword in keywords):
            return dev_type
    if (vendor or "").lower().startswith(_PHONE_VENDORS) or (random_mac and not hostname):
        return DeviceType.PHONE
    return DeviceType.UNKNOWN


def _reverse_dns(ip: str) -> str | None:
    try:
        name = socket.gethostbyaddr(ip)[0].rstrip(".")
    except (OSError, UnicodeError):
        return None
    return name if name and name != ip else None


class HostnameResolver:
    def __init__(self, *, timeout: float = 3.0, ttl_hit: float = 3600, ttl_miss: float = 600, workers: int = 16):
        self._timeout = timeout
        self._ttl_hit = ttl_hit
        self._ttl_miss = ttl_miss
        self._pool = cf.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="rdns")
        self._cache: dict[str, tuple[str | None, float]] = {}
        self._pending: dict[str, cf.Future[str | None]] = {}
        self._lock = threading.Lock()

    def resolve(self, ips: Sequence[str]) -> dict[str, str | None]:
        now = time.monotonic()
        result: dict[str, str | None] = {}
        waiting: dict[str, cf.Future[str | None]] = {}
        with self._lock:
            for ip in ips:
                cached = self._cache.get(ip)
                if cached and cached[1] > now:
                    result[ip] = cached[0]
                    continue
                future = self._pending.get(ip)
                if future is None:
                    future = self._pending[ip] = self._pool.submit(_reverse_dns, ip)
                waiting[ip] = future

        # gethostbyaddr can block for seconds; slow lookups are collected on a later scan.
        cf.wait(waiting.values(), timeout=self._timeout)

        with self._lock:
            for ip, future in waiting.items():
                if future.done():
                    self._pending.pop(ip, None)
                    name = future.result()
                    self._cache[ip] = (name, now + (self._ttl_hit if name else self._ttl_miss))
                    result[ip] = name
                else:
                    stale = self._cache.get(ip)
                    result[ip] = stale[0] if stale else None
        return result

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


class Enricher:
    def __init__(self, network: NetworkInfo, resolver: HostnameResolver | None = None) -> None:
        self._network = network
        self._resolver = resolver

    def enrich(self, found: Sequence[Found]) -> list[Observation]:
        missing = [f.ip for f in found if not f.hostname]
        names = self._resolver.resolve(missing) if self._resolver and missing else {}
        return [self._observe(f, f.hostname or names.get(f.ip)) for f in found]

    def _observe(self, found: Found, hostname: str | None) -> Observation:
        vendor = found.vendor or vendor_for(found.mac)
        random_mac = is_random_mac(found.mac)
        is_self = found.mac == self._network.self_mac
        is_gateway = found.ip == self._network.gateway
        return Observation(
            mac=found.mac,
            ip=found.ip,
            rtt_ms=found.rtt_ms,
            vendor=vendor,
            hostname=hostname,
            dev_type=guess_type(vendor, hostname, random_mac=random_mac, is_gateway=is_gateway, is_self=is_self),
            random_mac=random_mac,
            is_self=is_self,
            is_gateway=is_gateway,
        )

    def close(self) -> None:
        if self._resolver:
            self._resolver.close()
