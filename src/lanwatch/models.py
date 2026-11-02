from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, TypedDict


class DeviceType(StrEnum):
    ROUTER = "router"
    PHONE = "phone"
    TABLET = "tablet"
    COMPUTER = "computer"
    TV = "tv"
    CONSOLE = "console"
    SPEAKER = "speaker"
    PRINTER = "printer"
    CAMERA = "camera"
    SERVER = "server"
    IOT = "iot"
    UNKNOWN = "unknown"


class EventKind(StrEnum):
    NEW = "new"
    ONLINE = "online"
    OFFLINE = "offline"
    IP_CHANGE = "ip_change"


PresenceMark = Literal[0, 1] | None


@dataclass(frozen=True, slots=True)
class Notice:
    code: str
    params: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Found:
    ip: str
    mac: str
    rtt_ms: float | None = None
    hostname: str | None = None
    vendor: str | None = None


@dataclass(frozen=True, slots=True)
class Observation:
    mac: str
    ip: str
    rtt_ms: float | None
    vendor: str | None
    hostname: str | None
    dev_type: DeviceType
    random_mac: bool = False
    is_self: bool = False
    is_gateway: bool = False


@dataclass(frozen=True, slots=True)
class Device:
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


@dataclass(frozen=True, slots=True)
class Event:
    ts: float
    mac: str
    kind: EventKind
    ip: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class EventView:
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


@dataclass(frozen=True, slots=True)
class ScanRecord:
    id: int
    started: float
    duration: float
    found: int
    method: str
    error: str | None


class DeviceEdit(TypedDict, total=False):
    alias: str | None
    dev_type: DeviceType | Literal["auto"]
    known: bool
    notes: str | None
