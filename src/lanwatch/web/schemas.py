from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..models import DeviceType, EventKind, PresenceMark


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mac: str
    ip: str
    hostname: str | None
    vendor: str | None
    alias: str | None
    dev_type: DeviceType
    type_locked: bool
    notes: str | None
    known: bool
    random_mac: bool
    is_self: bool
    is_gateway: bool
    online: bool
    rtt_ms: float | None
    first_seen: float
    last_seen: float
    is_new: bool
    presence: list[PresenceMark]


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: float
    mac: str
    kind: EventKind
    ip: str | None
    detail: str | None
    alias: str | None
    hostname: str | None
    vendor: str | None
    dev_type: DeviceType | None


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started: float
    duration: float
    found: int
    method: str
    error: str | None


class ScanStatus(BaseModel):
    scanning: bool
    interval: int
    offline_after: int
    method: str | None
    error: str | None
    last: ScanOut | None


class NetworkOut(BaseModel):
    interface: str | None
    subnets: list[str]
    gateway: str | None
    self_ip: str | None
    self_mac: str | None


class NoticeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    params: dict[str, str]


class Stats(BaseModel):
    total: int
    online: int
    offline: int
    new: int
    unknown: int


class StateOut(BaseModel):
    now: float
    version: str
    demo: bool
    network: NetworkOut
    scan: ScanStatus
    notices: list[NoticeOut]
    stats: Stats
    devices: list[DeviceOut]
    events: list[EventOut]


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str | None = Field(default=None, max_length=64)
    dev_type: DeviceType | Literal["auto"] | None = None
    known: bool | None = None
    notes: str | None = Field(default=None, max_length=500)


class ScanQueued(BaseModel):
    queued: bool
    scanning: bool


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
