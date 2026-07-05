# Storage behavior tests are written before meter_cam_ingest.storage exists.
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from meter_cam_ingest.storage import month_key, store_capture


JPEG_ONE = b"\xff\xd8" + b"one" * 1024 + b"\xff\xd9"
JPEG_TWO = b"\xff\xd8" + b"two" * 1024 + b"\xff\xd9"


def test_month_key_uses_warsaw_timezone() -> None:
    warsaw_now = datetime(2026, 6, 28, 0, 1, 4, tzinfo=ZoneInfo("Europe/Warsaw"))

    assert month_key(warsaw_now) == "2026-06"


def test_store_capture_writes_image_and_latest_metadata(tmp_path: Path) -> None:
    now = datetime(2026, 6, 28, 0, 1, 4, 123456, tzinfo=ZoneInfo("Europe/Warsaw"))

    metadata = store_capture(tmp_path, "water", "m5stack-timercam-water", JPEG_ONE, now)

    image_path = Path(metadata["image_path"])
    latest_path = tmp_path / "captures" / "water" / "2026-06" / "latest.json"

    assert metadata["ok"] is True
    assert metadata["meter_id"] == "water"
    assert metadata["device_id"] == "m5stack-timercam-water"
    assert metadata["month"] == "2026-06"
    assert metadata["bytes"] == len(JPEG_ONE)
    assert image_path.exists()
    assert image_path.read_bytes() == JPEG_ONE
    assert image_path.name.endswith(".jpg")
    assert latest_path.exists()
    latest = json.loads(latest_path.read_text())
    assert latest == metadata


def test_store_capture_preserves_duplicate_uploads_and_updates_latest(tmp_path: Path) -> None:
    now = datetime(2026, 6, 28, 0, 1, 4, 123456, tzinfo=ZoneInfo("Europe/Warsaw"))

    first = store_capture(tmp_path, "water", "m5stack-timercam-water", JPEG_ONE, now)
    second = store_capture(tmp_path, "water", "m5stack-timercam-water", JPEG_TWO, now)

    first_path = Path(first["image_path"])
    second_path = Path(second["image_path"])
    latest_path = tmp_path / "captures" / "water" / "2026-06" / "latest.json"
    latest = json.loads(latest_path.read_text())

    assert first_path.exists()
    assert second_path.exists()
    assert first_path != second_path
    assert first_path.read_bytes() == JPEG_ONE
    assert second_path.read_bytes() == JPEG_TWO
    assert latest["image_path"] == second["image_path"]
