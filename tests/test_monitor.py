from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from lanwatch.models import Found
from lanwatch.runtime import Services

from .conftest import FakeScanner


def test_scanning_host_is_added_to_results(make_services: Callable[..., Services]) -> None:
    services = make_services()
    result = services.monitor.scan_once()
    assert result is not None
    assert {ob.ip for ob in result.created} == {"10.0.0.1", "10.0.0.2", "10.0.0.20"}
    assert services.monitor.last_method == "fake"


def test_failed_scan_is_reported_without_marking_devices_offline(
    make_services: Callable[..., Services], scanner: FakeScanner
) -> None:
    services = make_services()
    services.monitor.scan_once()
    scanner.error = RuntimeError("interface down")

    assert services.monitor.scan_once() is None
    assert services.monitor.last_error == "interface down"
    assert all(device.online for device in services.storage.devices())


def test_scan_requests_are_coalesced(make_services: Callable[..., Services]) -> None:
    monitor = make_services().monitor
    assert monitor.request_scan()
    assert not monitor.request_scan()
    assert monitor.busy


@pytest.fixture
def webhook() -> Iterator[tuple[str, list[dict[str, Any]]]]:
    received: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/hook", received
    server.shutdown()


def test_new_devices_trigger_one_webhook_each(
    make_services: Callable[..., Services],
    scanner: FakeScanner,
    webhook: tuple[str, list[dict[str, Any]]],
) -> None:
    url, received = webhook
    scanner.found = [Found("10.0.0.30", "b8:27:eb:00:00:30", 1.0)]
    services = make_services(webhook_url=url)
    services.monitor.scan_once()
    services.monitor.scan_once()

    assert sorted(p["mac"] for p in received) == ["02:00:00:00:00:02", "b8:27:eb:00:00:30"]
    pi = next(p for p in received if p["mac"] == "b8:27:eb:00:00:30")
    assert pi["event"] == "new_device"
    assert pi["vendor"] == "Raspberry Pi Foundation"
    assert pi["type"] == "server"
