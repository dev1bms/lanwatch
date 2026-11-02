from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .demo import DemoScanner
from .enrichment import Enricher, HostnameResolver
from .monitor import Monitor
from .network import NetworkInfo, detect_network
from .notifier import WebhookNotifier
from .scanners import Scanner, build_scanner
from .storage import Storage


@dataclass(frozen=True, slots=True)
class Services:
    settings: Settings
    network: NetworkInfo
    storage: Storage
    enricher: Enricher
    monitor: Monitor

    def close(self) -> None:
        self.enricher.close()
        self.storage.close()


def build_services(
    settings: Settings,
    *,
    network: NetworkInfo | None = None,
    storage: Storage | None = None,
    scanner: Scanner | None = None,
) -> Services:
    storage = storage or Storage(settings.db_path)
    demo = DemoScanner() if settings.demo and scanner is None else None

    if demo:
        network = network or demo.network()
        scanner = demo
    network = network or detect_network(settings.subnets, settings.interface)
    scanner = scanner or build_scanner(settings, network)

    resolver = HostnameResolver() if settings.resolve_hostnames and not settings.demo else None
    enricher = Enricher(network, resolver)
    if demo:
        demo.seed(storage, enricher, offline_after=settings.offline_timeout)

    monitor = Monitor(
        settings=settings,
        network=network,
        storage=storage,
        scanner=scanner,
        enricher=enricher,
        notifier=WebhookNotifier(str(settings.webhook_url)) if settings.webhook_url else None,
    )
    return Services(settings, network, storage, enricher, monitor)
