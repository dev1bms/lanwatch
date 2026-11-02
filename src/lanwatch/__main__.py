from __future__ import annotations

import logging
import sys

import uvicorn
from pydantic import ValidationError

from .config import Settings
from .web import create_app


def main() -> None:
    try:
        settings = Settings()
    except ValidationError as exc:
        sys.exit(f"Invalid configuration:\n{exc}")

    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        access_log=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
