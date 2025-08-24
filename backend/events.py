from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Set
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BusStats:
    published: int = 0
    dropped_ws: int = 0
    subscribers: int = 0


class EventBus:
    """
    Simple in-process async fan-out bus with per-subscriber bounded queues.
    publish() must be called from the event loop thread.
    publish_threadsafe() can be called from other threads.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, client_queue_size: int = 1000) -> None:
        self._loop = loop
        self._subs: Set[asyncio.Queue] = set()
        self._client_queue_size = client_queue_size
        self._stats = BusStats()
        self._lock = asyncio.Lock()

    @property
    def stats(self) -> BusStats:
        s = BusStats(
            published=self._stats.published,
            dropped_ws=self._stats.dropped_ws,
            subscribers=len(self._subs),
        )
        return s

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._client_queue_size)
        async with self._lock:
            self._subs.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subs.discard(q)

    def publish_threadsafe(self, event: Dict[str, Any]) -> None:
        # schedule on the loop to avoid cross-thread access to queues
        self._loop.call_soon_threadsafe(asyncio.create_task, self.publish(event))

    async def publish(self, event: Dict[str, Any]) -> None:
        self._stats.published += 1
        remove: List[asyncio.Queue] = []
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest one and insert newest
                try:
                    _ = q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                self._stats.dropped_ws += 1
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    # Client is too slow; schedule removal
                    remove.append(q)
        if remove:
            async with self._lock:
                for q in remove:
                    self._subs.discard(q)
