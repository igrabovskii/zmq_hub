from __future__ import annotations

import base64
import logging
import threading
from typing import Any, Dict, List

import zmq

from .config import Settings
from .events import EventBus, now_iso
from .zmq_monitor import monitor_loop

log = logging.getLogger("zmqhub.proxy")


def _encode_part(b: bytes) -> tuple[str, str]:
    try:
        s = b.decode("utf-8")
        return s, "utf8"
    except UnicodeDecodeError:
        return base64.b64encode(b).decode("ascii"), "base64"


def _build_bus_event(source: str, frames: List[bytes]) -> Dict[str, Any]:
    topic_b, topic_enc = _encode_part(frames[0] if frames else b"")
    parts_enc: List[str] = []
    payload: Any
    if len(frames) <= 1:
        payload = None
    elif len(frames) == 2:
        s, enc = _encode_part(frames[1])
        payload = s
        parts_enc = [enc]
    else:
        payload_list: List[str] = []
        for p in frames[1:]:
            s, enc = _encode_part(p)
            payload_list.append(s)
            parts_enc.append(enc)
        payload = payload_list
    ev: Dict[str, Any] = {
        "ts": now_iso(),
        "kind": "bus",
        "source": source,
        "topic": topic_b,
        "payload": payload,
        "meta": {
            "topic_encoding": topic_enc,
            "payload_encodings": parts_enc,
            "parts": len(frames),
            "sizes": [len(x) for x in frames],
        },
    }
    return ev


class Proxy:
    def __init__(self, settings: Settings, bus: EventBus) -> None:
        self.settings = settings
        self.bus = bus
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._mon_threads: list[threading.Thread] = []
        self._context: zmq.Context | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="zmqhub-proxy", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        for t in self._mon_threads:
            t.join(timeout=1.0)
        self._mon_threads.clear()
        if self._context is not None:
            try:
                self._context.term()
            except Exception:
                pass
            self._context = None

    def _run(self) -> None:
        ctx = zmq.Context(io_threads=1)
        self._context = ctx

        xsub = ctx.socket(zmq.XSUB)
        xsub.set_hwm(self.settings.xsub_rcvhwm)
        xsub.setsockopt(zmq.LINGER, self.settings.linger_ms)
        xsub.bind(self.settings.xsub_bind)

        xpub = ctx.socket(zmq.XPUB)
        xpub.set_hwm(self.settings.xpub_sndhwm)
        xpub.setsockopt(zmq.XPUB_VERBOSE, 1)
        xpub.setsockopt(zmq.LINGER, self.settings.linger_ms)
        xpub.bind(self.settings.xpub_bind)

        # Monitors
        try:
            xsub_mon = xsub.get_monitor_socket()
            xpub_mon = xpub.get_monitor_socket()
            t1 = threading.Thread(
                target=monitor_loop, args=(xsub_mon, "xsub", self.bus, self._stop), daemon=True, name="zmqhub-mon-xsub"
            )
            t2 = threading.Thread(
                target=monitor_loop, args=(xpub_mon, "xpub", self.bus, self._stop), daemon=True, name="zmqhub-mon-xpub"
            )
            t1.start()
            t2.start()
            self._mon_threads.extend([t1, t2])
        except Exception:
            log.exception("Failed to start monitor sockets")

        poller = zmq.Poller()
        poller.register(xsub, zmq.POLLIN)
        poller.register(xpub, zmq.POLLIN)

        log.info("Proxy running: XSUB %s <-> XPUB %s", self.settings.xsub_bind, self.settings.xpub_bind)
        try:
            while not self._stop.is_set():
                try:
                    events = dict(poller.poll(timeout=100))
                except zmq.error.ZMQError as e:
                    if e.errno == zmq.ETERM:
                        break
                    raise

                if xsub in events and events[xsub] & zmq.POLLIN:
                    try:
                        msg = xsub.recv_multipart(flags=zmq.NOBLOCK)
                    except zmq.Again:
                        msg = None
                    if msg:
                        # forward publish frames from publishers -> subscribers
                        xpub.send_multipart(msg)
                        # capture -> bus
                        self.bus.publish_threadsafe(_build_bus_event("xsub", msg))

                if xpub in events and events[xpub] & zmq.POLLIN:
                    try:
                        # subscription updates from subscribers -> forward to xsub
                        sub_msg = xpub.recv_multipart(flags=zmq.NOBLOCK)
                    except zmq.Again:
                        sub_msg = None
                    if sub_msg:
                        xsub.send_multipart(sub_msg)
        finally:
            try:
                xsub.disable_monitor()
            except Exception:
                pass
            try:
                xpub.disable_monitor()
            except Exception:
                pass
            try:
                xsub.close(self.settings.linger_ms)
            except Exception:
                pass
            try:
                xpub.close(self.settings.linger_ms)
            except Exception:
                pass
            try:
                ctx.term()
            except Exception:
                pass
