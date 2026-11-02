from lanwatch.models import DeviceType, EventKind, Observation
from lanwatch.storage import DAY, MIGRATIONS, Storage

from .conftest import observation

A, B = "aa:aa:aa:aa:aa:01", "aa:aa:aa:aa:aa:02"
BUCKET = DAY / 48


def save(storage: Storage, observations: list[Observation], at: float) -> None:
    storage.save_scan(observations, started=at, finished=at, method="test", offline_after=300)


def test_schema_is_versioned(storage: Storage) -> None:
    assert storage._conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)


def test_scan_lifecycle_is_persisted(storage: Storage) -> None:
    save(storage, [observation(A, "10.0.0.2"), observation(B, "10.0.0.3")], at=1000)
    save(storage, [observation(A, "10.0.0.2")], at=1400)

    device_b = storage.device(B)
    assert device_b is not None
    assert not device_b.online
    assert [e.kind for e in storage.events()] == [EventKind.OFFLINE, EventKind.NEW, EventKind.NEW]
    last = storage.last_scan()
    assert last is not None
    assert last.found == 1


def test_user_edits_survive_scans(storage: Storage) -> None:
    save(storage, [observation(A, "10.0.0.2", DeviceType.PHONE, hostname="iphone")], at=1000)
    storage.update_device(A, {"alias": "  Kitchen tablet ", "known": True, "dev_type": DeviceType.TABLET})
    save(storage, [observation(A, "10.0.0.2", DeviceType.PHONE)], at=1060)

    device = storage.device(A)
    assert device is not None
    assert device.alias == "Kitchen tablet"
    assert device.known
    assert device.dev_type is DeviceType.TABLET
    assert device.hostname == "iphone"

    storage.update_device(A, {"dev_type": "auto", "alias": ""})
    save(storage, [observation(A, "10.0.0.2", DeviceType.PHONE)], at=1120)
    device = storage.device(A)
    assert device is not None
    assert device.dev_type is DeviceType.PHONE
    assert device.alias is None


def test_update_unknown_device_returns_none(storage: Storage) -> None:
    assert storage.update_device(A, {"known": True}) is None
    assert storage.update_device(A, {}) is None


def test_presence_distinguishes_absent_from_no_data(storage: Storage) -> None:
    now = 100_000.0
    save(storage, [observation(A, "10.0.0.2"), observation(B, "10.0.0.3")], at=now - 3 * BUCKET)
    save(storage, [observation(A, "10.0.0.2")], at=now - BUCKET)

    presence = storage.presence(now=now)
    assert presence[A][-3:] == [1, None, 1]
    assert presence[B][-3:] == [1, None, 0]
    assert presence["ff:ff:ff:ff:ff:ff"][-1] == 0


def test_failed_scan_does_not_touch_devices(storage: Storage) -> None:
    save(storage, [observation(A, "10.0.0.2")], at=1000)
    storage.save_failed_scan(started=5000, finished=5001, method="arp", error="boom")
    device = storage.device(A)
    assert device is not None
    assert device.online
    last = storage.last_scan()
    assert last is not None
    assert last.error == "boom"


def test_delete_and_prune(storage: Storage) -> None:
    save(storage, [observation(A, "10.0.0.2")], at=1000)
    assert storage.delete_device(A)
    assert storage.device(A) is None
    assert storage.events() == []
    assert not storage.delete_device(A)

    save(storage, [observation(A, "10.0.0.2")], at=1000)
    later = 1000 + 8 * DAY
    storage.prune(now=later, history_days=7)
    assert storage.presence(now=later)[A] == [None] * 48
