from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from .config import Settings
from .events import EventBus, now_iso
from .hub import Hub
from .logging_config import setup_logging

log = logging.getLogger("zmqhub.app")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="ZeroMQ Hub", version="0.1.0")
# Allow all origins by default; adjust via proxy/CDN if needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Serve static UI
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=False), name="static")


@app.on_event("startup")
async def on_startup() -> None:
    settings = Settings()
    setup_logging(settings)
    loop = asyncio.get_running_loop()
    bus = EventBus(loop=loop, client_queue_size=settings.client_queue_size)
    hub = Hub(settings=settings, bus=bus)
    app.state.settings = settings
    app.state.bus = bus
    app.state.hub = hub
    hub.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    hub: Hub = app.state.hub
    hub.stop()


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/healthz")
async def healthz() -> JSONResponse:
    hub: Hub = app.state.hub
    return JSONResponse(hub.health())


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket) -> None:
    await ws.accept()
    bus: EventBus = app.state.bus
    q = await bus.subscribe()
    try:
        while True:
            event = await q.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        await bus.unsubscribe(q)


@app.websocket("/ws/control")
async def ws_control(ws: WebSocket) -> None:
    await ws.accept()
    hub: Hub = app.state.hub
    try:
        while True:
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                await ws.send_json({"ok": False, "error": "invalid_json"})
                continue
            action = (data.get("action") or "").lower()
            if action == "ping":
                await ws.send_json({"action": "pong", "ts": now_iso()})
            elif action == "publish":
                topic = data.get("topic") or ""
                payload = data.get("payload")
                encoding = (data.get("encoding") or "utf8").lower()
                multipart = data.get("multipart")
                if not isinstance(topic, str) or not topic:
                    await ws.send_json({"ok": False, "error": "topic must be a non-empty string"})
                    continue
                if encoding not in ("utf8", "base64"):
                    await ws.send_json({"ok": False, "error": "encoding must be 'utf8' or 'base64'"})
                    continue
                if multipart is not None and not (isinstance(multipart, list) and all(isinstance(x, str) for x in multipart)):
                    await ws.send_json({"ok": False, "error": "multipart must be an array of base64 strings"})
                    continue
                try:
                    hub.publish(topic=topic, payload=payload, encoding=encoding, multipart=multipart)
                    await ws.send_json({"ok": True})
                except Exception as e:
                    await ws.send_json({"ok": False, "error": str(e)})
            elif action in ("subscribe", "set_filter"):
                # Not implemented yet; acknowledge as no-op
                await ws.send_json({"ok": True})
            else:
                await ws.send_json({"ok": False, "error": "unknown_action"})
    except WebSocketDisconnect:
        pass
