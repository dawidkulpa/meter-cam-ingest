# Implementation Plan: Meter Camera Ingest Service

**Branch**: `feat/meter-camera-ingest-service` | **Date**: 2026-07-05 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/kitty-specs/meter-camera-ingest-service-01KWSKRQ/spec.md`

## Summary

Build a small Python standard-library HTTP service that accepts token-authenticated raw JPEG uploads from the monthly water-meter camera, stores each valid image immutably under a month directory, and atomically updates `latest.json` for Hermes cron to consume. The service owns only capture ingest and durable handoff; Hermes owns all LLM, validation, Telegram, approval, and email workflow.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Python standard library only at runtime (`http.server`, `pathlib`, `json`, `hashlib`, `hmac`, `zoneinfo`, `tempfile`, `os`)  
**Storage**: Filesystem under configurable root, default `/srv/meter-cam`; no database  
**Testing**: pytest-based automated tests for storage and HTTP behavior; `python3 -m compileall` for syntax verification; manual local curl smoke test  
**Target Platform**: Debian/Linux on the Hermes VM, running under systemd as `metercam`  
**Project Type**: single Python service/package  
**Performance Goals**: Handle one monthly camera upload plus occasional manual retries; reject bodies above configured max before reading excessive data; respond to local health checks immediately  
**Constraints**: LAN-only HTTP MVP; token-authenticated capture endpoint; no third-party runtime dependencies; no LLM/email/Telegram/n8n/S3 logic in service; no secret values committed or logged  
**Scale/Scope**: One meter camera endpoint (`/capture/water`), one image per normal month, multiple retries preserved per month

## Charter Check

No project-specific charter exists yet. Apply mission constraints from the spec:

- Keep the ingest boundary deliberately dumb.
- Use strict TDD for production code.
- Prefer simple inspectable file state over a database.
- Preserve downstream evidence; never overwrite existing image captures.
- Do not introduce external runtime services or dependencies for the MVP.

## Project Structure

### Documentation (this mission)

```text
kitty-specs/meter-camera-ingest-service-01KWSKRQ/
├── spec.md
├── plan.md
├── tasks.md
├── checklists/
│   └── requirements.md
└── tasks/
    ├── README.md
    ├── WP01-project-scaffold-and-storage.md
    ├── WP02-http-capture-api.md
    └── WP03-docs-deploy-and-smoke-test.md
```

### Source Code (repository root)

```text
meter_cam_ingest/
├── __init__.py
├── server.py
└── storage.py

tests/
├── fixtures/
│   └── tiny.jpg
├── test_server.py
└── test_storage.py

deploy/
├── meter-cam-ingest.env.example
└── meter-cam-ingest.service

README.md
pyproject.toml
```

**Structure Decision**: Use a single Python package at repository root because this is one small service with two responsibilities: HTTP request handling and atomic filesystem storage. Keep deploy samples in `deploy/` and tests in `tests/`.

## Complexity Tracking

No charter violations. The chosen approach is the simplest viable architecture for the camera-to-Hermes handoff.

## Implementation Concern Map

### IC-01 — Project scaffold and runtime shape

- **Purpose**: Establish package metadata, importable modules, tests, and a generated JPEG fixture without introducing runtime dependencies.
- **Relevant requirements**: FR-010, FR-013, FR-014, NFR-001, NFR-005, NFR-006
- **Affected surfaces**: `pyproject.toml`, `meter_cam_ingest/__init__.py`, `tests/fixtures/tiny.jpg`, `README.md`
- **Sequencing/depends-on**: none
- **Risks**: Accidentally adding production dependencies or committing secrets.

### IC-02 — Atomic capture storage

- **Purpose**: Persist valid capture bytes and metadata in a durable month-based layout that Hermes can read safely.
- **Relevant requirements**: FR-006, FR-007, FR-008, FR-009, FR-012, NFR-002
- **Affected surfaces**: `meter_cam_ingest/storage.py`, `tests/test_storage.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: Partial writes, same-second filename collisions, wrong timezone month, or unreadable metadata paths.

### IC-03 — HTTP ingest API and validation

- **Purpose**: Provide the service boundary for camera uploads with deterministic auth, validation, status codes, and JSON responses.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-010, FR-011, NFR-003, NFR-004
- **Affected surfaces**: `meter_cam_ingest/server.py`, `tests/test_server.py`
- **Sequencing/depends-on**: IC-02
- **Risks**: Reading oversized bodies, leaking tokens, non-JSON errors, or accepting invalid content.

### IC-04 — Deployment and operator handoff

- **Purpose**: Make the service deployable and understandable for the Hermes VM without implementing downstream Hermes workflow.
- **Relevant requirements**: FR-013, FR-014, NFR-003
- **Affected surfaces**: `deploy/meter-cam-ingest.service`, `deploy/meter-cam-ingest.env.example`, `README.md`
- **Sequencing/depends-on**: IC-03
- **Risks**: systemd sandbox blocking writes, private GitHub repo clone assumptions, or docs implying the service owns LLM/email approval logic.

## Implementation Strategy

Use vertical TDD slices:

1. Write scaffold/import tests, watch them fail, add package skeleton.
2. Write storage behavior tests, watch each fail, implement minimal storage code.
3. Write HTTP behavior tests, watch each fail, implement minimal server code.
4. Add docs and deployment samples after executable behavior is green.
5. Run full automated tests, compileall, and a manual local curl upload smoke test before final commit.

## Verification Plan

Commands required before completion:

```bash
python3 -m compileall meter_cam_ingest
pytest -q
python3 -m meter_cam_ingest.server  # in background with test env for smoke only
curl -s http://127.0.0.1:<port>/health
curl -i -X POST -H 'Content-Type: image/jpeg' -H 'X-Api-Key: ...' -H 'X-Device-Id: m5stack-timercam-water' --data-binary @tests/fixtures/tiny.jpg http://127.0.0.1:<port>/capture/water
```

Smoke test must prove `latest.json` and the uploaded JPEG exist under the configured temporary storage root.
