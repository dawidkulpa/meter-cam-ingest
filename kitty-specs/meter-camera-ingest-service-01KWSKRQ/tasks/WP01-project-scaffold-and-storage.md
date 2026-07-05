---
work_package_id: WP01
title: Project scaffold and atomic storage
dependencies: []
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- FR-012
tracker_refs: []
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
agent: ''
history:
- timestamp: '2026-07-05T17:08:00Z'
  agent: hermes
  action: Prompt generated via Spec Kitty tasks planning
agent_profile: python-pedro
authoritative_surface: meter_cam_ingest/storage.py
create_intent:
- pyproject.toml
- meter_cam_ingest/__init__.py
- meter_cam_ingest/storage.py
- tests/fixtures/tiny.jpg
- tests/test_storage.py
execution_mode: code_change
owned_files:
- pyproject.toml
- meter_cam_ingest/__init__.py
- meter_cam_ingest/storage.py
- tests/fixtures/tiny.jpg
- tests/test_storage.py
role: implementer
tags: []
---

# Work Package Prompt: WP01 – Project scaffold and atomic storage

## ⚡ Do This First: Load Agent Profile

Load the Python implementation profile before changing files. If using Spec Kitty agent surfaces, run the assigned profile-loading step for `python-pedro`; otherwise follow strict Python TDD discipline manually.

## Objective

Create the importable Python package and implement the atomic filesystem storage layer for monthly meter camera uploads.

## Context

The service accepts raw JPEG uploads later in WP02. This WP owns the durable handoff primitives only. It must preserve every valid image, compute the Europe/Warsaw month key, atomically update `latest.json`, and avoid overwriting existing captures under rapid retries.

## Requirements Covered

FR-006, FR-007, FR-008, FR-009, FR-010, FR-012, NFR-001, NFR-002, NFR-005, NFR-006

## Detailed Guidance

### T001 — Create Python package metadata and repository runtime skeleton

- Create `pyproject.toml` with project metadata and pytest config.
- Production runtime must not require third-party dependencies.
- Test dependencies may use pytest.

### T002 — Create importable package and generated tiny JPEG fixture

- Create `meter_cam_ingest/__init__.py`.
- Create `meter_cam_ingest/storage.py` with no behavior initially.
- Generate a tiny valid JPEG fixture at `tests/fixtures/tiny.jpg` for tests.

### T003 — Write failing storage tests

Write tests before implementation and run them to verify they fail for missing behavior:

- `month_key` returns `2026-06` for a June Europe/Warsaw datetime.
- `store_capture` creates `<root>/captures/water/<YYYY-MM>/`.
- `store_capture` writes the exact image bytes to an immutable `.jpg` file.
- `store_capture` writes `latest.json` pointing to the image path.
- A second upload in the same second/month keeps both image files and updates `latest.json` to the second upload.

### T004 — Implement atomic filesystem storage

Implement minimal behavior to pass tests:

- SHA-256 hashing.
- Filename-safe timezone-aware timestamp including microseconds.
- Collision-safe final path selection.
- Atomic write helpers using temp files and `os.replace`.
- Metadata JSON with `ok`, `meter_id`, `device_id`, `month`, `received_at`, `sha256`, `bytes`, and `image_path`.

### T005 — Run verification

Run:

```bash
python3 -m compileall meter_cam_ingest
pytest tests/test_storage.py -q
```

## Definition of Done

- Storage tests pass.
- Compileall passes.
- No HTTP server code is added in this WP except imports required by tests.
- No runtime third-party dependency is introduced.

## Risks for Reviewer

- Check that same-second uploads cannot overwrite each other.
- Check that `latest.json` is updated only after the JPEG exists.
- Check that timezone is not accidentally UTC-only.
