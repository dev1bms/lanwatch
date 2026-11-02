from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable

from .config import Settings
from .enrichment import Enricher
from .models import Found, Notice
from .network import NetworkInfo
from .notifier import Notifier
from .reconcile import Reconciliation
from .scanners import Scanner
from .storage import Storage

log = logging.getLogger(__name__)

PRUNE_INTERVAL = 3600.0


class Monitor:
    def __init__(
        self,
        *,
        settings: Settings,
        network: NetworkInfo,
        storage: Storage,
        scanner: Scanner,
        enricher: Enricher,
        notifier: Notifier | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._settings = settings
        self._network = network
        self._storage = storage
        self._scanner = scanner
        self._enricher = enricher
        self._notifier = notifier
        self._clock = clock
        self._wake: asyncio.Event | None = None
        self._last_prune = 0.0
        self._scanning = False
        self._requested = False
        self.last_method: str | None = None
        self.last_error: str | None = None

    @property
    def busy(self) -> bool:
        return self._scanning or self._requested

    @property
    def notices(self) -> tuple[Notice, ...]:
        return self._network.notices + self._scanner.notices

    def request_scan(self) -> bool:
        if self.busy:
            return False
        self._requested = True
        if self._wake is not None:
            self._wake.set()
        return True

    async def run(self) -> None:
        self._wake = asyncio.Event()
        while True:
            self._requested = False
            self._scanning = True
            try:
                await asyncio.to_thread(self.scan_once)
            except Exception:
                log.exception("scan crashed")
            finally:
                self._scanning = False
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=self._settings.scan_interval)
            self._wake.clear()

    def scan_once(self) -> Reconciliation | None:
        started = self._clock()
        try:
            found = self._scanner.scan()
        except Exception as exc:
            self.last_error = str(exc) or type(exc).__name__
            log.warning("scan via %s failed: %s", self._scanner.name, self.last_error)
            # A failed scan says nothing about the devices, so none of them may be marked offline.
            self._storage.save_failed_scan(
                started=started, finished=self._clock(), method=self._scanner.name, error=self.last_error
            )
            return None

        observations = self._enricher.enrich(self._with_self(found))
        finished = self._clock()
        result = self._storage.save_scan(
            observations,
            started=started,
            finished=finished,
            method=self._scanner.name,
            offline_after=self._settings.offline_timeout,
        )
        self.last_method = self._scanner.name
        self.last_error = None
        log.debug("scan via %s: %d devices in %.1fs", self.last_method, len(observations), finished - started)

        if result.created:
            log.info("new devices: %s", ", ".join(ob.mac for ob in result.created))
            if self._notifier:
                self._notifier.new_devices(result.created, finished)

        if finished - self._last_prune > PRUNE_INTERVAL:
            self._storage.prune(now=finished, history_days=self._settings.history_days)
            self._last_prune = finished
        return result

    def _with_self(self, found: list[Found]) -> list[Found]:
        # A host never answers its own ARP request.
        ip, mac = self._network.self_ip, self._network.self_mac
        if not ip or not mac or not self._network.contains(ip) or any(f.mac == mac for f in found):
            return found
        return [*found, Found(ip=ip, mac=mac, rtt_ms=0.0)]
