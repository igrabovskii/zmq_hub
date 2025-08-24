from __future__ import annotations

import base64
import logging
import threading
from typing import Any, Dict

import zmq
from zmq.utils.monitor import recv_monitor_message

from .events import EventBus, now_iso

log = logging.getLogger("zmqhub.monitor")

EVENT_NAMES = {getattr(zmq, name): name for name in dir(zmq) if name.startswith("EVENT_")}


def _endpoint_to_str(ep: Any) -> str:
    if isinstance(ep, bytes):
        try:
            return ep.decode("utf-8", errors="replace")
        except Exception:
            return base64.b64encode(ep).decode("ascii")
    return str(ep)


def monitor_loop(monitor_sock: zmq.Socket, source: str, bus: EventBus, stop: threading.Event) -> None:
    """Run in a thread: read monitor events and push to bus."""
    try:
        while not stop.is_set():
            try:
                evt = recv_monitor_message(monitor_sock, flags=zmq.NOBLOCK)
            except zmq.Again:
                if stop.wait(0.05):
                    break
                continue
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break
                log.exception("Monitor socket error")
                break
            if not evt:
                continue
            ev_code = evt.get("event")
            ev_name = EVENT_NAMES.get(ev_code, str(ev_code))
            payload: Dict[str, Any] = {
                "ts": now_iso(),
                "kind": "monitor",
                "source": source,
                "topic": None,
                "payload": None,
                "meta": {
                    "event": ev_name,
                    "value": evt.get("value"),
                    "endpoint": _endpoint_to_str(evt.get("endpoint")),
                    "errno": evt.get("error"),
                },
            }
            bus.publish_threadsafe(payload)
    finally:
        try:
            monitor_sock.close(0)
        except Exception:
            pass
