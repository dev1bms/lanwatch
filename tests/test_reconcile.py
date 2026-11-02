from lanwatch.models import Device, DeviceType, EventKind
from lanwatch.reconcile import reconcile

from .conftest import observation


def device(mac: str, ip: str, **fields: object) -> Device:
    values: dict[str, object] = {
        "mac": mac,
        "ip": ip,
        "hostname": None,
        "vendor": None,
        "alias": None,
        "dev_type": DeviceType.UNKNOWN,
        "type_locked": False,
        "notes": None,
        "known": False,
        "random_mac": False,
        "is_self": False,
        "is_gateway": False,
        "online": True,
        "rtt_ms": None,
        "first_seen": 0.0,
        "last_seen": 1000.0,
    }
    return Device(**(values | fields))


A, B = "aa:aa:aa:aa:aa:01", "aa:aa:aa:aa:aa:02"


def test_unknown_mac_is_created_with_new_event() -> None:
    result = reconcile({}, [observation(A, "10.0.0.2")], now=1000, offline_after=300)
    assert [ob.mac for ob in result.created] == [A]
    assert [e.kind for e in result.events] == [EventKind.NEW]


def test_silent_device_stays_online_within_grace_period() -> None:
    result = reconcile({B: device(B, "10.0.0.3", last_seen=1000)}, [], now=1200, offline_after=300)
    assert result.went_offline == []
    assert result.events == []


def test_silent_device_goes_offline_after_grace_period() -> None:
    result = reconcile({B: device(B, "10.0.0.3", last_seen=1000)}, [], now=1400, offline_after=300)
    assert result.went_offline == [B]
    assert [e.kind for e in result.events] == [EventKind.OFFLINE]


def test_returning_device_on_new_address_emits_online_and_ip_change() -> None:
    known = {B: device(B, "10.0.0.3", online=False)}
    result = reconcile(known, [observation(B, "10.0.0.9")], now=1500, offline_after=300)
    events = {e.kind: e for e in result.events}
    assert set(events) == {EventKind.ONLINE, EventKind.IP_CHANGE}
    assert events[EventKind.IP_CHANGE].detail == "10.0.0.3"
    assert events[EventKind.IP_CHANGE].ip == "10.0.0.9"


def test_merge_keeps_known_details_and_locked_type() -> None:
    known = {A: device(A, "10.0.0.2", hostname="iphone", dev_type=DeviceType.TABLET, type_locked=True)}
    (merged,) = reconcile(known, [observation(A, "10.0.0.2", DeviceType.PHONE)], now=1100, offline_after=300).refreshed
    assert merged.hostname == "iphone"
    assert merged.dev_type is DeviceType.TABLET


def test_unknown_guess_does_not_replace_a_better_one() -> None:
    known = {A: device(A, "10.0.0.2", dev_type=DeviceType.TV)}
    (merged,) = reconcile(known, [observation(A, "10.0.0.2")], now=1100, offline_after=300).refreshed
    assert merged.dev_type is DeviceType.TV


def test_duplicate_observations_are_counted_once() -> None:
    result = reconcile({}, [observation(A, "10.0.0.2"), observation(A, "10.0.0.2")], now=1000, offline_after=300)
    assert len(result.created) == 1
