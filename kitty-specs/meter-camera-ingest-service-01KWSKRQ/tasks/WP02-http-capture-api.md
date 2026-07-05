---
work_package_id: WP02
title: HTTP capture API and validation
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-010
- FR-011
- FR-012
tracker_refs: []
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - API
agent: ''
history:
- timestamp: '2026-07-05T17:08:00Z'
  agent: hermes
  action: Prompt generated via Spec Kitty tasks planning
agent_profile: python-pedro
authoritative_surface: meter_cam_ingest/server.py
create_intent:
- meter_cam_ingest/server.py
- tests/test_server.py
execution_mode: code_change
owned_files:
- meter_cam_ingest/server.py
- tests/test_server.py
role: implementer
tags: []
---

# Work Package Prompt: WP02 – HTTP capture API and validation

## ⚡ Do This First: Load Agent Profile

Load the Python implementation profile before changing files. If using Spec Kitty agent surfaces, run the assigned profile-loading step for `python-pedro`; otherwise follow strict Python TDD discipline manually.

## Objective

Implement the standard-library HTTP service that exposes `/health` and `/capture/water` with token auth, device allowlist validation, upload validation, and JSON responses.

## Context

WP01 provides `store_capture`. WP02 must turn that storage primitive into the camera-facing service boundary without adding framework runtime dependencies. Every response should be JSON. The API key must never appear in responses or logs.

## Requirements Covered

FR-001, FR-002, FR-003, FR-004, FR-005, FR-010, FR-011, FR-012, NFR-003, NFR-004, NFR-005

## Detailed Guidance

### T006 — Write failing HTTP tests

Write tests first and verify they fail for missing server behavior:

- `GET /health` returns JSON 200.
- Missing/wrong `X-Api-Key` returns JSON 401.
- Unknown `X-Device-Id` returns JSON 403 when allowlist is configured.
- Wrong content type returns JSON 415.
- Missing content length returns JSON 411.
- Invalid content length returns JSON 400.
- Oversized body returns JSON 413 without storing a file.
- Too-small or non-JPEG body returns JSON 400.
- Valid JPEG upload returns JSON 201 and writes files through `store_capture`.

### T007 — Implement environment config and JSON response helpers

- Parse env vars with defaults from the spec.
- Require `METER_CAM_API_KEY` for production serving.
- Keep config construction testable without mutating global environment in tests.
- Implement stable JSON error payloads.

### T008 — Implement HTTP handler

- Use `ThreadingHTTPServer` and `BaseHTTPRequestHandler`.
- Use `hmac.compare_digest` for token comparison.
- Parse media type from `Content-Type` before accepting `image/jpeg`.
- Validate `Content-Length` before reading the request body.
- Call `store_capture` only after all auth and validation checks pass.

### T009 — Run verification

Run:

```bash
python3 -m compileall meter_cam_ingest
pytest tests/test_server.py -q
pytest -q
```

## Definition of Done

- HTTP tests pass.
- Full test suite passes.
- All responses are JSON.
- No runtime third-party dependency is introduced.
- Storage contract from WP01 remains unchanged.

## Risks for Reviewer

- Check that invalid uploads do not create files.
- Check that `Content-Length` is enforced before reading large bodies.
- Check that the API key cannot leak in errors/logs.
