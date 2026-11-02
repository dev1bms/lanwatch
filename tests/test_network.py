from ipaddress import IPv4Network
from pathlib import Path

import pytest

from lanwatch import network
from lanwatch.network import Route


def test_routes_are_parsed_from_proc(tmp_path: Path) -> None:
    route_file = tmp_path / "route"
    route_file.write_text(
        "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT\n"
        "eth0\t00000000\t0101A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n"
        "eth0\t0001A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0\n"
    )
    routes = network.read_routes(route_file)
    assert network.default_route(routes) == ("eth0", "192.168.1.1")
    assert routes[1].dest == "192.168.1.0"
    assert routes[1].mask == "255.255.255.0"


@pytest.fixture
def wide_lan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network, "read_routes", lambda: [Route("eth0", "0.0.0.0", "10.1.0.1", 3, "0.0.0.0")])
    monkeypatch.setattr(network, "interface_ipv4", lambda _: ("10.1.2.3", "255.255.0.0"))
    monkeypatch.setattr(network, "interface_mac", lambda _: "aa:bb:cc:dd:ee:ff")


@pytest.mark.usefixtures("wide_lan")
def test_large_detected_network_is_narrowed() -> None:
    info = network.detect_network()
    assert info.subnets == (IPv4Network("10.1.2.0/24"),)
    assert [n.code for n in info.notices] == ["net_narrowed"]
    assert info.contains("10.1.2.200")
    assert not info.contains("10.1.3.1")


@pytest.mark.usefixtures("wide_lan")
def test_configured_subnets_are_validated() -> None:
    info = network.detect_network(subnets=("10.0.0.0/8", "bad", "10.1.0.0/20"))
    assert info.subnets == (IPv4Network("10.1.0.0/20"),)
    assert [n.code for n in info.notices] == ["subnet_too_large", "subnet_invalid"]
