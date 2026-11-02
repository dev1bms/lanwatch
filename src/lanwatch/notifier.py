from __future__ import annotations

import json
import logging
import urllib.request
from collections.abc import Sequence
from typing import Protocol

from .models import Observation

log = logging.getLogger(__name__)


class Notifier(Protocol):
    def new_devices(self, devices: Sequence[Observation], when: float) -> None: ...


class WebhookNotifier:
    def __init__(self, url: str, *, timeout: float = 5.0) -> None:
        self._url = url
        self._timeout = timeout

    def new_devices(self, devices: Sequence[Observation], when: float) -> None:
        for device in devices:
            label = device.hostname or device.vendor or device.mac
            self._post(
                {
                    "event": "new_device",
                    "text": f"New device on the network: {label} ({device.ip}, {device.mac})",
                    "mac": device.mac,
                    "ip": device.ip,
                    "vendor": device.vendor,
                    "hostname": device.hostname,
                    "type": device.dev_type.value,
                    "ts": when,
                }
            )

    def _post(self, payload: dict[str, object]) -> None:
        request = urllib.request.Request(
            self._url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "LanWatch"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout):
                pass
        except OSError as exc:
            log.warning("webhook delivery failed: %s", exc)
