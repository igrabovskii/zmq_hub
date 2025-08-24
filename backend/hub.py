from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .config import Settings
from .events import EventBus
from .publisher import Publisher
from .zmq_proxy import Proxy

log = logging.getLogger("zmqhub.hub")


class Hub:
    def __init__(self, settings: Settings, bus: EventBus) -> None:
        self.settings = settings
        self.bus = bus
        self._proxy = Proxy(settings, bus)
        self._publisher = Publisher(settings, bus)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._proxy.start()
        self._publisher.start()
        self._started = True
        log.info("Hub started")

    def stop(self) -> None:
        if not self._started:
            return
        self._proxy.stop()
        self._publisher.stop()
        self._started = False
        log.info("Hub stopped")

    def publish(self, *, topic: str, payload: Optional[str], encoding: str, multipart: Optional[list[str]]) -> None:
        self._publisher.publish(topic=topic, payload=payload, encoding=encoding, multipart=multipart)

    def health(self) -> Dict[str, Any]:
        stats = self.bus.stats
        return {
            "status": "ok" if self._started else "starting",
            "xsub_bind": self.settings.xsub_bind,
            "xpub_bind": self.settings.xpub_bind,
            "inject_connect": self.settings.inject_connect,
            "bus": {
                "published": stats.published,
                "dropped_ws": stats.dropped_ws,
                "subscribers": stats.subscribers,
            },
        }
