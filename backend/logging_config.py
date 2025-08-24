from __future__ import annotations

import json
import logging
from typing import Any, Dict

from .config import Settings


def setup_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(level)


def log_json(logger: logging.Logger, level: int, msg: str, **kwargs: Any) -> None:
    payload: Dict[str, Any] = {"msg": msg}
    payload.update(kwargs)
    logger.log(level, json.dumps(payload, separators=(",", ":")))
