from __future__ import annotations

import base64
import sqlite3
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from lanwatch.runtime import Services

ClientFactory = Callable[..., tuple[TestClient, Services]]


def basic(credentials: str) -> dict[str, str]:
    return {"Authorization": f"Basic {base64.b64encode(credentials.encode()).decode()}"}


def test_state_describes_network_devices_and_events(make_client: ClientFactory) -> None:
    client, _ = make_client()
    response = client.get("/api/state")
    state = response.json()

    assert response.headers["cache-control"] == "no-store"
    assert state["network"]["subnets"] == ["10.0.0.0/24"]
    assert state["stats"] == {"total": 3, "online": 3, "offline": 0, "new": 3, "unknown": 3}
    by_ip = {device["ip"]: device for device in state["devices"]}
    assert by_ip["10.0.0.1"]["dev_type"] == "router"
    assert by_ip["10.0.0.2"]["is_self"]
    assert by_ip["10.0.0.20"]["dev_type"] == "phone"
    assert len(by_ip["10.0.0.20"]["presence"]) == 48
    assert {event["kind"] for event in state["events"]} == {"new"}


def test_device_update_validation_and_delete(make_client: ClientFactory) -> None:
    client, _ = make_client()
    mac = "F0-18-98-4E-21-9A"

    response = client.patch(f"/api/devices/{mac}", json={"alias": "Phone", "known": True, "dev_type": "tablet"})
    assert response.status_code == 200
    assert response.json()["alias"] == "Phone"
    assert response.json()["type_locked"]

    assert client.patch(f"/api/devices/{mac}", json={"dev_type": "fridge"}).status_code == 422
    assert client.patch(f"/api/devices/{mac}", json={"admin": True}).status_code == 422
    assert client.patch(f"/api/devices/{mac}", json={"alias": "x" * 65}).status_code == 422
    assert client.patch("/api/devices/not-a-mac", json={}).status_code == 422
    assert client.patch("/api/devices/00:00:00:00:00:99", json={}).status_code == 404

    assert client.delete(f"/api/devices/{mac}").status_code == 204
    assert client.delete(f"/api/devices/{mac}").status_code == 404


def test_scan_endpoint_queues_once(make_client: ClientFactory) -> None:
    client, _ = make_client()
    assert client.post("/api/scan").json() == {"queued": True, "scanning": True}
    assert client.post("/api/scan").json()["queued"] is False


def test_events_limit_is_bounded(make_client: ClientFactory) -> None:
    client, _ = make_client()
    assert len(client.get("/api/events", params={"limit": 1}).json()) == 1
    assert client.get("/api/events", params={"limit": 0}).status_code == 422


def test_basic_auth_protects_everything_but_health(make_client: ClientFactory) -> None:
    client, _ = make_client(auth="admin:s3cret")
    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 401
    assert client.get("/api/state").status_code == 401
    assert client.get("/api/state", headers=basic("admin:wrong")).status_code == 401
    assert client.get("/api/state", headers={"Authorization": "Basic !!!"}).status_code == 401
    assert client.get("/api/state", headers=basic("admin:s3cret")).status_code == 200


def test_dashboard_assets_are_served(make_client: ClientFactory) -> None:
    client, _ = make_client()
    assert "LanWatch" in client.get("/").text
    for path in (
        "/static/js/main.js",
        "/static/css/app.css",
        "/static/locales/en.json",
        "/static/locales/ar.json",
        "/static/fonts/readex-pro-arabic-400-normal.woff2",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["cache-control"] == "no-cache"


def test_lifespan_closes_services(make_client: ClientFactory) -> None:
    client, services = make_client()
    with client:
        assert client.get("/api/health").json()["status"] == "ok"
    with pytest.raises(sqlite3.ProgrammingError):
        services.storage.devices()
