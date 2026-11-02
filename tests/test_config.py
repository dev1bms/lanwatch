import pytest
from pydantic import ValidationError

from .conftest import make_settings


def test_subnets_accept_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LW_SUBNETS", "192.168.1.0/24, 192.168.50.0/24,")
    assert make_settings().subnets == ("192.168.1.0/24", "192.168.50.0/24")


def test_empty_env_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LW_INTERFACE", "")
    monkeypatch.setenv("LW_AUTH", "")
    settings = make_settings()
    assert settings.interface is None
    assert settings.auth is None


def test_offline_timeout_scales_with_interval() -> None:
    assert make_settings().offline_timeout == 300
    assert make_settings(scan_interval=200).offline_timeout == 600
    assert make_settings(scan_interval=60, offline_after=120).offline_timeout == 120


@pytest.mark.parametrize(
    "overrides",
    [{"auth": "no-colon"}, {"scan_interval": 5}, {"scan_interval": 60, "offline_after": 30}, {"scan_method": "x"}],
)
def test_invalid_settings_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_settings(**overrides)
