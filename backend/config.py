from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # HTTP/WS server
    http_host: str = "0.0.0.0"
    http_port: int = 8080

    # ZMQ binds (external clients)
    xsub_bind: str = "tcp://0.0.0.0:5551"  # publishers connect here
    xpub_bind: str = "tcp://0.0.0.0:5552"  # subscribers connect here

    # Injection path (internal publisher -> hub XSUB)
    inject_connect: str = "tcp://127.0.0.1:5551"

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # WebSocket limits
    ws_max_msg_size: int = 2 * 1024 * 1024

    # Event buffering and backpressure
    event_queue_size: int = 10000
    client_queue_size: int = 1000

    # Heartbeats
    heartbeat_interval_s: float = 15.0

    # Logging
    log_level: str = "INFO"
    log_json: bool = False

    # ZMQ tuning (basic)
    xsub_rcvhwm: int = 10000
    xpub_sndhwm: int = 10000
    linger_ms: int = 0

    class Config:
        env_prefix = "ZMQHUB_"
        env_file = ".env"
        extra = "ignore"
