from __future__ import annotations

import http.client
import json
import socket
import threading
from pathlib import Path

import pytest

from meter_cam_ingest.server import Config, make_server


JPEG = b"\xff\xd8" + b"valid" * 600 + b"\xff\xd9"


@pytest.fixture
def running_server(tmp_path: Path):
    config = Config(
        bind_host="127.0.0.1",
        port=0,
        root=tmp_path,
        api_key="test-secret",
        timezone="Europe/Warsaw",
        max_bytes=4096,
        min_bytes=10,
        allowed_device_ids={"m5stack-timercam-water"},
    )
    server = make_server(config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield host, port, tmp_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request(host: str, port: int, method: str, path: str, body: bytes = b"", headers: dict[str, str] | None = None):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request(method, path, body=body, headers=headers or {})
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, json.loads(data.decode("utf-8"))


def test_health_returns_json_ok(running_server) -> None:
    host, port, _ = running_server

    status, payload = request(host, port, "GET", "/health")

    assert status == 200
    assert payload == {"ok": True, "service": "meter-cam-ingest"}


def test_unknown_path_returns_json_404(running_server) -> None:
    host, port, _ = running_server

    status, payload = request(host, port, "GET", "/nope")

    assert status == 404
    assert payload["ok"] is False
    assert payload["error"] == "not_found"


def test_wrong_method_returns_json_405(running_server) -> None:
    host, port, _ = running_server

    status, payload = request(host, port, "PUT", "/capture/water")

    assert status == 405
    assert payload["ok"] is False
    assert payload["error"] == "method_not_allowed"


def test_capture_rejects_missing_token(running_server) -> None:
    host, port, _ = running_server

    status, payload = request(host, port, "POST", "/capture/water", JPEG, {"Content-Type": "image/jpeg"})

    assert status == 401
    assert payload["ok"] is False
    assert payload["error"] == "unauthorized"


def test_capture_rejects_wrong_token_without_leaking_secret(running_server) -> None:
    host, port, _ = running_server

    status, payload = request(
        host,
        port,
        "POST",
        "/capture/water",
        JPEG,
        {"Content-Type": "image/jpeg", "X-Api-Key": "wrong", "X-Device-Id": "m5stack-timercam-water"},
    )

    assert status == 401
    assert payload["error"] == "unauthorized"
    assert "test-secret" not in json.dumps(payload)


def test_capture_rejects_unknown_device(running_server) -> None:
    host, port, _ = running_server

    status, payload = request(
        host,
        port,
        "POST",
        "/capture/water",
        JPEG,
        {"Content-Type": "image/jpeg", "X-Api-Key": "test-secret", "X-Device-Id": "unknown"},
    )

    assert status == 403
    assert payload["error"] == "forbidden_device"


def test_capture_rejects_wrong_content_type(running_server) -> None:
    host, port, _ = running_server

    status, payload = request(
        host,
        port,
        "POST",
        "/capture/water",
        JPEG,
        {"Content-Type": "application/octet-stream", "X-Api-Key": "test-secret", "X-Device-Id": "m5stack-timercam-water"},
    )

    assert status == 415
    assert payload["error"] == "unsupported_media_type"


def test_capture_rejects_oversized_body(running_server) -> None:
    host, port, root = running_server

    status, payload = request(
        host,
        port,
        "POST",
        "/capture/water",
        b"\xff\xd8" + b"x" * 5000,
        {"Content-Type": "image/jpeg", "X-Api-Key": "test-secret", "X-Device-Id": "m5stack-timercam-water"},
    )

    assert status == 413
    assert payload["error"] == "payload_too_large"
    assert not (root / "captures").exists()


def test_capture_rejects_too_small_body(running_server) -> None:
    host, port, _ = running_server

    status, payload = request(
        host,
        port,
        "POST",
        "/capture/water",
        b"\xff\xd8",
        {"Content-Type": "image/jpeg", "X-Api-Key": "test-secret", "X-Device-Id": "m5stack-timercam-water"},
    )

    assert status == 400
    assert payload["error"] == "body_too_small"


def test_capture_rejects_non_jpeg_body(running_server) -> None:
    host, port, _ = running_server

    status, payload = request(
        host,
        port,
        "POST",
        "/capture/water",
        b"not a jpeg body",
        {"Content-Type": "image/jpeg", "X-Api-Key": "test-secret", "X-Device-Id": "m5stack-timercam-water"},
    )

    assert status == 400
    assert payload["error"] == "invalid_jpeg"


def test_capture_rejects_missing_content_length(running_server) -> None:
    host, port, _ = running_server
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall(
            b"POST /capture/water HTTP/1.1\r\n"
            + f"Host: {host}:{port}\r\n".encode()
            + b"Content-Type: image/jpeg\r\n"
            + b"X-Api-Key: test-secret\r\n"
            + b"X-Device-Id: m5stack-timercam-water\r\n"
            + b"Connection: close\r\n\r\n"
            + JPEG
        )
        raw = sock.recv(4096)

    assert b"411" in raw.split(b"\r\n", 1)[0]
    assert b"length_required" in raw


def test_capture_rejects_invalid_content_length(running_server) -> None:
    host, port, _ = running_server
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall(
            b"POST /capture/water HTTP/1.1\r\n"
            + f"Host: {host}:{port}\r\n".encode()
            + b"Content-Type: image/jpeg\r\n"
            + b"Content-Length: abc\r\n"
            + b"X-Api-Key: test-secret\r\n"
            + b"X-Device-Id: m5stack-timercam-water\r\n"
            + b"Connection: close\r\n\r\n"
            + JPEG
        )
        raw = sock.recv(4096)

    assert b"400" in raw.split(b"\r\n", 1)[0]
    assert b"invalid_content_length" in raw


def test_valid_capture_writes_files(running_server) -> None:
    host, port, root = running_server

    status, payload = request(
        host,
        port,
        "POST",
        "/capture/water",
        JPEG,
        {"Content-Type": "image/jpeg; charset=binary", "X-Api-Key": "test-secret", "X-Device-Id": "m5stack-timercam-water"},
    )

    assert status == 201
    assert payload["ok"] is True
    assert payload["meter_id"] == "water"
    image_path = Path(payload["image_path"])
    latest_path = root / "captures" / "water" / payload["month"] / "latest.json"
    assert image_path.exists()
    assert image_path.read_bytes() == JPEG
    assert latest_path.exists()
    assert json.loads(latest_path.read_text()) == payload
