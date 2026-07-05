"""Atomic filesystem storage for meter camera captures."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def month_key(now: datetime) -> str:
    """Return YYYY-MM for a timezone-aware datetime."""
    return now.strftime("%Y-%m")


def safe_timestamp(now: datetime) -> str:
    """Return an ISO-like timestamp safe for filenames."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.isoformat(timespec="microseconds").replace(":", "-")


def sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 digest for bytes."""
    return hashlib.sha256(data).hexdigest()


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise


def atomic_write_bytes(path: Path, data: bytes, mode: int = 0o664) -> None:
    """Atomically write raw bytes to path."""
    _atomic_write(path, data, mode)


def atomic_write_json(path: Path, payload: dict, mode: int = 0o664) -> None:
    """Atomically write a JSON object to path."""
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    _atomic_write(path, encoded, mode)


def _unique_image_path(month_dir: Path, timestamp: str, digest: str) -> Path:
    stem = f"{timestamp}__{digest[:16]}"
    candidate = month_dir / f"{stem}.jpg"
    if not candidate.exists():
        return candidate
    counter = 1
    while True:
        candidate = month_dir / f"{stem}__{counter}.jpg"
        if not candidate.exists():
            return candidate
        counter += 1


def store_capture(
    root: Path | str,
    meter_id: str,
    device_id: str,
    body: bytes,
    now: datetime,
) -> dict:
    """Store one validated capture and update latest metadata.

    The caller is responsible for validating auth, size, and JPEG magic.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    root_path = Path(root)
    month = month_key(now)
    month_dir = root_path / "captures" / meter_id / month
    month_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(month_dir, 0o775)

    digest = sha256_bytes(body)
    image_path = _unique_image_path(month_dir, safe_timestamp(now), digest)
    atomic_write_bytes(image_path, body)

    latest_path = month_dir / "latest.json"
    metadata = {
        "ok": True,
        "meter_id": meter_id,
        "device_id": device_id,
        "month": month,
        "received_at": now.isoformat(),
        "sha256": digest,
        "bytes": len(body),
        "image_path": str(image_path),
        "latest_meta_path": str(latest_path),
    }
    atomic_write_json(latest_path, metadata)
    return metadata


def now_in_timezone(timezone_name: str) -> datetime:
    """Return current time in a named timezone."""
    return datetime.now(ZoneInfo(timezone_name))
