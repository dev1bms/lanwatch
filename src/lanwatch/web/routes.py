from __future__ import annotations

import re
import time
from dataclasses import asdict
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from .. import __version__
from ..models import Device, DeviceEdit, PresenceMark
from ..runtime import Services
from .schemas import (
    DeviceOut,
    DeviceUpdate,
    EventOut,
    Health,
    NetworkOut,
    NoticeOut,
    ScanOut,
    ScanQueued,
    ScanStatus,
    StateOut,
    Stats,
)

NEW_DEVICE_WINDOW = 86400.0
_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def get_services(request: Request) -> Services:
    return cast(Services, request.app.state.services)


def valid_mac(mac: str) -> str:
    normalized = mac.strip().lower().replace("-", ":")
    if not _MAC_RE.match(normalized):
        raise HTTPException(422, "Invalid MAC address")
    return normalized


ServicesDep = Annotated[Services, Depends(get_services)]
MacDep = Annotated[str, Depends(valid_mac)]

router = APIRouter(prefix="/api", dependencies=[Depends(_no_store)])


def _device_out(device: Device, presence: list[PresenceMark], now: float) -> DeviceOut:
    return DeviceOut(**asdict(device), is_new=device.first_seen >= now - NEW_DEVICE_WINDOW, presence=presence)


def _device_views(services: Services, now: float) -> list[DeviceOut]:
    presence = services.storage.presence(now=now)
    return [_device_out(device, presence[device.mac], now) for device in services.storage.devices()]


@router.get("/state")
def read_state(services: ServicesDep) -> StateOut:
    now = time.time()
    devices = _device_views(services, now)
    online = sum(device.online for device in devices)
    last_scan = services.storage.last_scan()
    network = services.network
    return StateOut(
        now=now,
        version=__version__,
        demo=services.settings.demo,
        network=NetworkOut(
            interface=network.interface,
            subnets=[str(net) for net in network.subnets],
            gateway=network.gateway,
            self_ip=network.self_ip,
            self_mac=network.self_mac,
        ),
        scan=ScanStatus(
            scanning=services.monitor.busy,
            interval=services.settings.scan_interval,
            offline_after=services.settings.offline_timeout,
            method=services.monitor.last_method,
            error=services.monitor.last_error,
            last=ScanOut.model_validate(last_scan) if last_scan else None,
        ),
        notices=[NoticeOut.model_validate(notice) for notice in services.monitor.notices],
        stats=Stats(
            total=len(devices),
            online=online,
            offline=len(devices) - online,
            new=sum(device.is_new for device in devices),
            unknown=sum(not device.known for device in devices),
        ),
        devices=devices,
        events=[EventOut.model_validate(event) for event in services.storage.events(limit=50)],
    )


@router.get("/devices")
def list_devices(services: ServicesDep) -> list[DeviceOut]:
    return _device_views(services, time.time())


@router.patch("/devices/{mac}")
def update_device(mac: MacDep, update: DeviceUpdate, services: ServicesDep) -> DeviceOut:
    device = services.storage.update_device(mac, cast(DeviceEdit, update.model_dump(exclude_unset=True)))
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    now = time.time()
    return _device_out(device, services.storage.presence(now=now)[mac], now)


@router.delete("/devices/{mac}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(mac: MacDep, services: ServicesDep) -> None:
    if not services.storage.delete_device(mac):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")


@router.get("/events")
def list_events(services: ServicesDep, limit: Annotated[int, Query(ge=1, le=500)] = 50) -> list[EventOut]:
    return [EventOut.model_validate(event) for event in services.storage.events(limit=limit)]


@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
async def request_scan(services: ServicesDep) -> ScanQueued:
    queued = services.monitor.request_scan()
    return ScanQueued(queued=queued, scanning=services.monitor.busy)


@router.get("/health")
def health() -> Health:
    return Health(version=__version__)
