"""Standard-library HTTP server for meter camera ingest."""

from __future__ import annotations

import hmac
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .storage import store_capture

SERVICE_NAME = "meter-cam-ingest"


@dataclass(frozen=True)
class Config:
    bind_host: str
    port: int
    root: Path
    api_key: str
    timezone: str = "Europe/Warsaw"
    max_bytes: int = 5_242_880
    min_bytes: int = 2_048
    allowed_device_ids: set[str] | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        values = env if env is not None else os.environ
        api_key = values.get("METER_CAM_API_KEY", "")
        if not api_key:
            raise ValueError("METER_CAM_API_KEY is required")
        allowed_raw = values.get("METER_CAM_ALLOWED_DEVICE_IDS", "m5stack-timercam-water")
        allowed = {item.strip() for item in allowed_raw.split(",") if item.strip()}
        return cls(
            bind_host=values.get("METER_CAM_BIND_HOST", "0.0.0.0"),
            port=int(values.get("METER_CAM_PORT", "8097")),
            root=Path(values.get("METER_CAM_ROOT", "/srv/meter-cam")),
            api_key=api_key,
            timezone=values.get("METER_CAM_TZ", "Europe/Warsaw"),
            max_bytes=int(values.get("METER_CAM_MAX_BYTES", "5242880")),
            min_bytes=int(values.get("METER_CAM_MIN_BYTES", "2048")),
            allowed_device_ids=allowed,
        )


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"


class MeterCamHandler(BaseHTTPRequestHandler):
    server_version = "MeterCamIngest/0.1"
    config: Config

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, code: str, message: str) -> None:
        self._send_json(status, {"ok": False, "error": code, "message": message})

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/health":
            self._send_json(200, {"ok": True, "service": SERVICE_NAME})
            return
        self._error(404, "not_found", "Unknown path")

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path != "/capture/water":
            self._error(404, "not_found", "Unknown path")
            return
        self._handle_capture("water")

    def do_PUT(self) -> None:  # noqa: N802
        self._error(405, "method_not_allowed", "Method not allowed")

    def do_DELETE(self) -> None:  # noqa: N802
        self._error(405, "method_not_allowed", "Method not allowed")

    def _handle_capture(self, meter_id: str) -> None:
        config = self.config

        token = self.headers.get("X-Api-Key", "")
        if not hmac.compare_digest(token, config.api_key):
            self._error(401, "unauthorized", "Missing or invalid API key")
            return

        device_id = self.headers.get("X-Device-Id", "")
        if config.allowed_device_ids and device_id not in config.allowed_device_ids:
            self._error(403, "forbidden_device", "Device ID is not allowed")
            return

        media_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if media_type != "image/jpeg":
            self._error(415, "unsupported_media_type", "Content-Type must be image/jpeg")
            return

        length_header = self.headers.get("Content-Length")
        if length_header is None:
            self._error(411, "length_required", "Content-Length is required")
            return
        try:
            content_length = int(length_header)
        except ValueError:
            self._error(400, "invalid_content_length", "Content-Length must be an integer")
            return

        if content_length > config.max_bytes:
            self._error(413, "payload_too_large", "Request body is too large")
            return
        if content_length < config.min_bytes:
            # Drain the small body so keep-alive clients do not confuse the next request.
            self.rfile.read(max(content_length, 0))
            self._error(400, "body_too_small", "Request body is too small")
            return

        body = self.rfile.read(content_length)
        if len(body) != content_length:
            self._error(400, "incomplete_body", "Request body ended early")
            return
        if not body.startswith(b"\xff\xd8"):
            self._error(400, "invalid_jpeg", "Request body is not a JPEG")
            return

        now = datetime.now(ZoneInfo(config.timezone))
        try:
            metadata = store_capture(config.root, meter_id, device_id, body, now)
        except Exception as exc:  # pragma: no cover - defensive; hard to trigger portably
            print(f"capture_store_failed meter_id={meter_id} device_id={device_id!r} error={exc}", file=sys.stderr)
            self._error(500, "storage_error", "Failed to store capture")
            return

        print(
            "capture_stored "
            f"meter_id={meter_id} device_id={device_id!r} month={metadata['month']} "
            f"bytes={metadata['bytes']} image_path={metadata['image_path']}",
            file=sys.stderr,
        )
        self._send_json(201, metadata)


def make_server(config: Config) -> ThreadingHTTPServer:
    class ConfiguredHandler(MeterCamHandler):
        pass

    ConfiguredHandler.config = config
    return ThreadingHTTPServer((config.bind_host, config.port), ConfiguredHandler)


def main() -> int:
    config = Config.from_env()
    server = make_server(config)
    host, port = server.server_address
    print(f"{SERVICE_NAME} listening on {host}:{port} root={config.root}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
