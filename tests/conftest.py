from __future__ import annotations

from collections.abc import Callable
from ipaddress import IPv4Network
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lanwatch.config import Settings
from lanwatch.models import DeviceType, Found, Notice, Observation
from lanwatch.network import NetworkInfo
from lanwatch.runtime import Services, build_services
from lanwatch.storage import Storage
from lanwatch.web import create_app

NETWORK = NetworkInfo("eth0", (IPv4Network("10.0.0.0/24"),), "10.0.0.1", "10.0.0.2", "02:00:00:00:00:02")


class FakeScanner:
    name = "fake"
    notices: tuple[Notice, ...] = ()

    def __init__(self, found: list[Found] | None = None) -> None:
        self.found = found or []
        self.error: Exception | None = None

    def scan(self) -> list[Found]:
        if self.error:
            raise self.error
        return list(self.found)


def make_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {"db_path": ":memory:", "resolve_hostnames": False}
    return Settings(_env_file=None, **(defaults | overrides))


def observation(mac: str, ip: str, dev_type: DeviceType = DeviceType.UNKNOWN, **fields: Any) -> Observation:
    return Observation(
        mac=mac, ip=ip, rtt_ms=1.0, vendor=fields.get("vendor"), hostname=fields.get("hostname"), dev_type=dev_type
    )


@pytest.fixture
def storage() -> Storage:
    return Storage(":memory:")


@pytest.fixture
def scanner() -> FakeScanner:
    return FakeScanner(
        [Found("10.0.0.1", "a4:91:b1:2c:00:01", 0.4), Found("10.0.0.20", "f0:18:98:4e:21:9a", 12.0, "iPhone.lan")]
    )


@pytest.fixture
def make_services(storage: Storage, scanner: FakeScanner) -> Callable[..., Services]:
    def factory(**settings: Any) -> Services:
        return build_services(make_settings(**settings), network=NETWORK, storage=storage, scanner=scanner)

    return factory


@pytest.fixture
def make_client(make_services: Callable[..., Services]) -> Callable[..., tuple[TestClient, Services]]:
    def factory(**settings: Any) -> tuple[TestClient, Services]:
        services = make_services(**settings)
        services.monitor.scan_once()
        return TestClient(create_app(services=services, start_monitor=False)), services

    return factory
