from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace

from .models import Device, DeviceType, Event, EventKind, Observation


@dataclass(slots=True)
class Reconciliation:
    created: list[Observation] = field(default_factory=list)
    refreshed: list[Observation] = field(default_factory=list)
    went_offline: list[str] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    @property
    def seen(self) -> list[Observation]:
        return [*self.created, *self.refreshed]


def resolve_type(device: Device, observed: DeviceType) -> DeviceType:
    if device.type_locked or observed is DeviceType.UNKNOWN:
        return device.dev_type
    return observed


def merge(device: Device, observation: Observation) -> Observation:
    return replace(
        observation,
        hostname=observation.hostname or device.hostname,
        vendor=observation.vendor or device.vendor,
        dev_type=resolve_type(device, observation.dev_type),
    )


def reconcile(
    known: Mapping[str, Device],
    observations: Iterable[Observation],
    *,
    now: float,
    offline_after: float,
) -> Reconciliation:
    result = Reconciliation()
    seen: set[str] = set()
    for observation in observations:
        if observation.mac in seen:
            continue
        seen.add(observation.mac)
        device = known.get(observation.mac)
        if device is None:
            result.created.append(observation)
            result.events.append(Event(now, observation.mac, EventKind.NEW, observation.ip))
            continue
        result.refreshed.append(merge(device, observation))
        if not device.online:
            result.events.append(Event(now, observation.mac, EventKind.ONLINE, observation.ip))
        if device.ip != observation.ip:
            result.events.append(Event(now, observation.mac, EventKind.IP_CHANGE, observation.ip, device.ip))

    cutoff = now - offline_after
    for mac, device in known.items():
        if mac not in seen and device.online and device.last_seen < cutoff:
            result.went_offline.append(mac)
            result.events.append(Event(now, mac, EventKind.OFFLINE, device.ip))
    return result
