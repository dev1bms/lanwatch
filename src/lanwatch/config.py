from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class ScanMethod(StrEnum):
    AUTO = "auto"
    ARP = "arp"
    NEIGH = "neigh"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LW_",
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    interface: str | None = None
    subnets: Annotated[tuple[str, ...], NoDecode] = ()
    scan_interval: int = Field(default=60, ge=10, le=3600)
    offline_after: int | None = Field(default=None, ge=10)
    scan_method: ScanMethod = ScanMethod.AUTO
    arp_timeout: float = Field(default=2.0, ge=0.5, le=30)
    arp_retry: int = Field(default=2, ge=0, le=10)
    resolve_hostnames: bool = True
    db_path: Path = Path("/data/lanwatch.db")
    host: str = "0.0.0.0"
    port: int = Field(default=8090, ge=1, le=65535)
    auth: SecretStr | None = None
    history_days: int = Field(default=7, ge=1, le=365)
    webhook_url: AnyHttpUrl | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    demo: bool = False

    @field_validator("subnets", mode="before")
    @classmethod
    def _split_subnets(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("auth")
    @classmethod
    def _check_auth(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and ":" not in value.get_secret_value():
            raise ValueError("must look like user:password")
        return value

    @model_validator(mode="after")
    def _check_offline_after(self) -> Self:
        if self.offline_after is not None and self.offline_after < self.scan_interval:
            raise ValueError("offline_after must be at least scan_interval")
        return self

    @property
    def offline_timeout(self) -> int:
        # Phones in Wi-Fi power-save mode regularly ignore a single ARP request.
        return self.offline_after or max(300, self.scan_interval * 3)
