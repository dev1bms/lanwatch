import pytest

from lanwatch.enrichment import Enricher, guess_type, is_random_mac, vendor_for
from lanwatch.models import DeviceType, Found

from .conftest import NETWORK


def test_vendor_lookup_is_offline_and_handles_unregistered_prefixes() -> None:
    assert vendor_for("b8:27:eb:00:00:01") == "Raspberry Pi Foundation"
    assert vendor_for("da:1e:77:0c:93:41") is None


@pytest.mark.parametrize(
    ("mac", "expected"),
    [("da:1e:77:0c:93:41", True), ("2e:00:00:00:00:00", True), ("f0:18:98:4e:21:9a", False), ("garbage", False)],
)
def test_random_mac_detection(mac: str, expected: bool) -> None:
    assert is_random_mac(mac) is expected


@pytest.mark.parametrize(
    ("vendor", "hostname", "flags", "expected"),
    [
        (None, None, {"is_gateway": True}, DeviceType.ROUTER),
        (None, None, {"is_self": True}, DeviceType.SERVER),
        ("Apple, Inc.", "MacBook-Air.home", {}, DeviceType.COMPUTER),
        ("Apple, Inc.", "iPad.home", {}, DeviceType.TABLET),
        ("Apple, Inc.", None, {}, DeviceType.PHONE),
        ("LG Electronics", "LGwebOSTV", {}, DeviceType.TV),
        ("Espressif Inc.", None, {}, DeviceType.IOT),
        ("TP-LINK TECHNOLOGIES CO.,LTD.", "Tapo-C200", {}, DeviceType.CAMERA),
        ("Brother Industries, LTD.", None, {}, DeviceType.PRINTER),
        (None, None, {"random_mac": True}, DeviceType.PHONE),
        (None, None, {}, DeviceType.UNKNOWN),
    ],
)
def test_guess_type(vendor: str | None, hostname: str | None, flags: dict[str, bool], expected: DeviceType) -> None:
    assert guess_type(vendor, hostname, **flags) is expected


def test_enricher_flags_gateway_and_self() -> None:
    gateway, server = Enricher(NETWORK).enrich(
        [Found("10.0.0.1", "a4:91:b1:2c:00:01"), Found("10.0.0.2", "02:00:00:00:00:02", hostname="pi")]
    )
    assert gateway.is_gateway
    assert gateway.dev_type is DeviceType.ROUTER
    assert server.is_self
    assert server.dev_type is DeviceType.SERVER
    assert server.random_mac
