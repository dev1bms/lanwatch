from pathlib import Path

import pytest

from lanwatch.config import ScanMethod
from lanwatch.models import Found
from lanwatch.network import NetworkInfo
from lanwatch.scanners import ArpScanner, AutoScanner, NeighborScanner, ScanError, ScanPermissionError, build_scanner

from .conftest import NETWORK, FakeScanner, make_settings


def test_neighbor_table_keeps_only_complete_entries_in_scope(tmp_path: Path) -> None:
    table = tmp_path / "arp"
    table.write_text(
        "IP address       HW type     Flags       HW address            Mask     Device\n"
        "10.0.0.1         0x1         0x2         A4:91:B1:2C:00:01     *        eth0\n"
        "10.0.0.7         0x1         0x0         00:00:00:00:00:00     *        eth0\n"
        "172.17.0.2       0x1         0x2         02:42:ac:11:00:02     *        docker0\n"
    )
    assert NeighborScanner(NETWORK, table=table).read_table() == [Found("10.0.0.1", "a4:91:b1:2c:00:01")]


def test_auto_scanner_falls_back_once_permission_is_denied() -> None:
    primary = FakeScanner()
    primary.error = ScanPermissionError("denied")
    fallback = FakeScanner([Found("10.0.0.5", "aa:aa:aa:aa:aa:05")])
    fallback.name = "neigh"
    scanner = AutoScanner(primary, fallback)

    assert scanner.scan() == fallback.found
    assert scanner.name == "neigh"
    assert [n.code for n in scanner.notices] == ["arp_no_permission"]

    primary.error = None
    assert scanner.scan() == fallback.found


def test_scanners_refuse_to_run_without_subnets() -> None:
    empty = NetworkInfo(None, (), None, None, None)
    with pytest.raises(ScanError, match="no subnet"):
        ArpScanner(empty).scan()


@pytest.mark.parametrize(
    ("method", "expected"),
    [(ScanMethod.ARP, ArpScanner), (ScanMethod.NEIGH, NeighborScanner), (ScanMethod.AUTO, AutoScanner)],
)
def test_build_scanner_honours_method(method: ScanMethod, expected: type) -> None:
    assert isinstance(build_scanner(make_settings(scan_method=method), NETWORK), expected)
