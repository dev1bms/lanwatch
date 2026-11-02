from __future__ import annotations

import random
import time
from datetime import datetime
from ipaddress import IPv4Network

from .enrichment import Enricher
from .models import Found, Notice
from .network import NetworkInfo
from .storage import Storage

SUBNET = IPv4Network("192.168.1.0/24")
GATEWAY = "192.168.1.1"
SELF_IP = "192.168.1.10"
SELF_MAC = "3c:7c:3f:10:aa:01"

Hours = tuple[tuple[float, float], ...]
ALWAYS: Hours = ((0.0, 24.0),)

HOUSEHOLD: tuple[tuple[int, str, str | None, str | None, Hours], ...] = (
    (1, "a4:91:b1:2c:00:01", "Sagemcom Broadband SAS", "router.home", ALWAYS),
    (21, "f0:18:98:4e:21:9a", "Apple, Inc.", "iPhone.home", ((0.0, 8.5), (14.0, 24.0))),
    (22, "8c:79:f5:31:5d:02", "Samsung Electronics Co.,Ltd", "Galaxy-S23.home", ALWAYS),
    (23, "da:1e:77:0c:93:41", None, None, ((7.0, 24.0),)),
    (24, "64:b4:73:aa:10:5e", "Xiaomi Communications Co Ltd", "Redmi-Note-12.home", ((0.0, 1.0), (8.0, 24.0))),
    (30, "c8:d0:83:77:1b:20", "Apple, Inc.", "MacBook-Air.home", ((9.0, 13.0), (15.0, 23.0))),
    (31, "a0:36:bc:5e:44:19", "ASUSTek COMPUTER INC.", "DESKTOP-7Q2M4L.home", ((10.0, 14.0), (17.0, 22.5))),
    (40, "58:fd:b1:02:6e:73", "LG Electronics", "LGwebOSTV.home", ((19.0, 23.5),)),
    (41, "48:d6:d5:91:0f:3a", "Google, Inc.", "Chromecast.home", ((19.0, 23.5),)),
    (45, "00:d9:d1:8e:22:c4", "Sony Interactive Entertainment Inc.", "PS5.home", ((17.0, 20.0),)),
    (50, "3c:2a:f4:19:7c:55", "Brother Industries, LTD.", "Brother-HL-L2350.home", ((9.0, 22.0),)),
    (60, "fc:65:de:38:91:0b", "Amazon Technologies Inc.", "Echo-Dot.home", ALWAYS),
    (61, "84:0d:8e:a1:3f:72", "Espressif Inc.", "plug-kitchen.home", ALWAYS),
    (62, "a8:42:a1:6e:0c:19", "TP-LINK TECHNOLOGIES CO.,LTD.", "Tapo-C200.home", ALWAYS),
    (70, "b0:be:83:22:9d:14", "Apple, Inc.", "iPad.home", ((16.0, 21.0),)),
)
NEWCOMER = (88, "2e:6b:1a:40:c7:e2", None, None, ALWAYS)


def _present(hours: Hours, ts: float) -> bool:
    moment = datetime.fromtimestamp(ts)
    hour = moment.hour + moment.minute / 60
    return any(start <= hour < end for start, end in hours)


class DemoScanner:
    name = "demo"
    notices: tuple[Notice, ...] = ()

    def __init__(self, *, seed: int = 7) -> None:
        self._rng = random.Random(seed)
        self._newcomer_since = time.time() - 3 * 3600

    @staticmethod
    def network() -> NetworkInfo:
        return NetworkInfo("eth0", (SUBNET,), GATEWAY, SELF_IP, SELF_MAC)

    def scan(self) -> list[Found]:
        return self._found_at(time.time())

    def seed(self, storage: Storage, enricher: Enricher, *, offline_after: float, step: float = 600.0) -> None:
        if not storage.is_empty():
            return
        now = time.time()
        first_seen = now - 7 * 86400
        moments = [first_seen, *(now - 86400 + i * step for i in range(int(86400 // step)))]
        for ts in moments:
            found = self._everyone() if ts == first_seen else self._found_at(ts)
            found.append(Found(SELF_IP, SELF_MAC, 0.0, "homeserver"))
            storage.save_scan(
                enricher.enrich(found),
                started=ts,
                finished=ts + self._rng.uniform(2, 5),
                method=self.name,
                offline_after=offline_after,
            )

    def _everyone(self) -> list[Found]:
        return [Found(f"192.168.1.{octet}", mac, 3.0, host, vendor) for octet, mac, vendor, host, _ in HOUSEHOLD]

    def _found_at(self, ts: float) -> list[Found]:
        devices = [*HOUSEHOLD, NEWCOMER] if ts >= self._newcomer_since else list(HOUSEHOLD)
        return [
            Found(f"192.168.1.{octet}", mac, round(self._rng.uniform(0.8, 42.0), 2), host, vendor)
            for octet, mac, vendor, host, hours in devices
            if _present(hours, ts)
        ]
