from __future__ import annotations

import base64
import logging
import queue
import threading
import time
from typing import List, Optional, Sequence

import zmq

from .config import Settings
from .events import EventBus, now_iso

log = logging.getLogger("zmqhub.publisher")


def _ensure_bytes(s: str, encoding: str = "utf8") -> bytes:
    if encoding == "utf8":
        return s.encode("utf-8")
    elif encoding == "base64":
        return base64.b64decode(s)
    else:
        raise ValueError(f"unsupported encoding: {encoding}")


def _build_frames(topic: str, payload: Optional[str], encoding: str, multipart: Optional[Sequence[str]]) -> List[bytes]:
    if not topic:
        raise ValueError("topic must be non-empty")
    frames: List[bytes] = [topic.encode("utf-8")]
    if multipart:
        for part_b64 in multipart:
            frames.append(base64.b64decode(part_b64))
    elif payload is not None:
        frames.append(_ensure_bytes(payload, encoding=encoding))
    return frames


class Publisher:
    """Background thread that holds a PUB socket to inject UI-originated messages into the hub via XSUB."""

    def __init__(self, settings: Settings, bus: EventBus) -> None:
        self.settings = settings
        self.bus = bus
        self._ctx: zmq.Context | None = None
        self._sock: zmq.Socket | None = None
        self._q: queue.Queue[List[bytes]] = queue.Queue(maxsize=1000)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="zmqhub-publisher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        try:
            if self._sock is not None:
                self._sock.close(0)
        finally:
            self._sock = None
            if self._ctx is not None:
                try:
                    self._ctx.term()
                except Exception:
                    pass
                self._ctx = None

    def publish(self, *, topic: str, payload: Optional[str] = None, encoding: str = "utf8", multipart: Optional[Sequence[str]] = None) -> None:
        frames = _build_frames(topic=topic, payload=payload, encoding=encoding, multipart=multipart)
        try:
            self._q.put(frames, timeout=1.0)
        except queue.Full:
            log.warning("Publisher queue full; dropping message")

    def _run(self) -> None:
        self._ctx = zmq.Context(io_threads=1)
        sock = self._ctx.socket(zmq.PUB)
        self._sock = sock
        sock.setsockopt(zmq.LINGER, self.settings.linger_ms)
        sock.set_hwm(10000)
        sock.connect(self.settings.inject_connect)
        log.info("Publisher connected to %s", self.settings.inject_connect)
        time.sleep(0.2)
        try:
            while not self._stop.is_set():
                try:
                    frames = self._q.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    sock.send_multipart(frames, flags=0)
                    topic = frames[0].decode("utf-8", errors="ignore")
                    self.bus.publish_threadsafe(
                        {
                            "ts": now_iso(),
                            "kind": "bus",
                            "source": "inject",
                            "topic": topic,
                            "payload": None if len(frames) <= 1 else (frames[1].decode("utf-8", errors="ignore") if len(frames) == 2 else ["<bytes>"] * (len(frames) - 1)),
                            "meta": {"ui_originated": True, "parts": len(frames), "sizes": [len(x) for x in frames]},
                        }
                    )
                except Exception:
                    log.exception("Failed to send injected message")
        finally:
            try:
                sock.close(self.settings.linger_ms)
            except Exception:
                pass
            try:
                self._ctx.term()
            except Exception:
                pass
