# Tasks: Meter Camera Ingest Service

**Mission**: `meter-camera-ingest-service-01KWSKRQ`  
**Spec**: [spec.md](./spec.md)  
**Plan**: [plan.md](./plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
| --- | --- | --- | --- |
| T001 | Create Python package metadata and repository runtime skeleton | WP01 | No |
| T002 | Create importable package and generated tiny JPEG fixture | WP01 | No |
| T003 | Write failing storage tests for month keys, metadata, and duplicate upload preservation | WP01 | No |
| T004 | Implement atomic filesystem storage until storage tests pass | WP01 | No |
| T005 | Run compileall and storage tests | WP01 | No |
| T006 | Write failing HTTP tests for health, auth, device allowlist, validation, and success cases | WP02 | No |
| T007 | Implement environment config and JSON response helpers | WP02 | No |
| T008 | Implement standard-library HTTP handler for `/health` and `/capture/water` | WP02 | No |
| T009 | Run compileall and full automated tests | WP02 | No |
| T010 | Add deployment samples for systemd and env configuration | WP03 | Yes |
| T011 | Add professional public README with boundaries, API examples, storage layout, and downstream handoff | WP03 | Yes |
| T012 | Run a local background-server curl smoke test and record verified commands in README | WP03 | No |
| T013 | Inspect git status for secrets and commit the completed spec/app artifacts | WP03 | No |

## Work Packages

### WP01 — Project scaffold and atomic storage

Summary: Create the app skeleton and implement the core file handoff behavior before any HTTP surface exists.  
Priority: High  
Independent test: `pytest tests/test_storage.py -q` and `python3 -m compileall meter_cam_ingest`  
Dependencies: none  
Prompt: [tasks/WP01-project-scaffold-and-storage.md](tasks/WP01-project-scaffold-and-storage.md)

Included subtasks:

- [ ] T001 Create Python package metadata and repository runtime skeleton (WP01)
- [ ] T002 Create importable package and generated tiny JPEG fixture (WP01)
- [ ] T003 Write failing storage tests for month keys, metadata, and duplicate upload preservation (WP01)
- [ ] T004 Implement atomic filesystem storage until storage tests pass (WP01)
- [ ] T005 Run compileall and storage tests (WP01)

Implementation sketch:

- Start with tests, verify failures, then add minimal package files.
- Implement `storage.py` with timezone-aware month calculation, hashing, collision-safe filenames, and atomic image/JSON writes.
- Keep all storage behavior independent from the HTTP server.

Parallel opportunities: none inside the WP; it establishes foundations for WP02.  
Risks: same-second filename collisions, partial writes, wrong timezone month, and accidental production dependencies.

### WP02 — HTTP capture API and validation

Summary: Add the standard-library HTTP server and all validation/auth behavior on top of the storage layer.  
Priority: High  
Independent test: `pytest tests/test_server.py -q && pytest -q`  
Dependencies: WP01  
Prompt: [tasks/WP02-http-capture-api.md](tasks/WP02-http-capture-api.md)

Included subtasks:

- [ ] T006 Write failing HTTP tests for health, auth, device allowlist, validation, and success cases (WP02)
- [ ] T007 Implement environment config and JSON response helpers (WP02)
- [ ] T008 Implement standard-library HTTP handler for `/health` and `/capture/water` (WP02)
- [ ] T009 Run compileall and full automated tests (WP02)

Implementation sketch:

- Use `ThreadingHTTPServer` and `BaseHTTPRequestHandler` only.
- Validate request headers and body before calling storage.
- Return JSON for every response and never include the API key in logs or response bodies.

Parallel opportunities: none; depends on storage behavior from WP01.  
Risks: reading oversized bodies, token leakage, non-JSON errors, and diverging from the exact handoff metadata contract.

### WP03 — Deployment samples, documentation, and smoke verification

Summary: Add operator-facing deployment/documentation artifacts and prove the finished service works through a local curl upload.  
Priority: Medium  
Independent test: `pytest -q`, `python3 -m compileall meter_cam_ingest`, and local curl smoke test  
Dependencies: WP02  
Prompt: [tasks/WP03-docs-deploy-and-smoke-test.md](tasks/WP03-docs-deploy-and-smoke-test.md)

Included subtasks:

- [ ] T010 Add deployment samples for systemd and env configuration (WP03)
- [ ] T011 Add professional public README with boundaries, API examples, storage layout, and downstream handoff (WP03)
- [ ] T012 Run a local background-server curl smoke test and record verified commands in README (WP03)
- [ ] T013 Inspect git status for secrets and commit the completed spec/app artifacts (WP03)

Implementation sketch:

- Add `deploy/` examples that match the spec's Linux/systemd assumptions.
- Document that the service does not own LLM/email/Telegram/n8n/S3 behavior using professional public-repository wording.
- Run a real local service process with a temporary root and verify health/upload/file output.

Parallel opportunities: `T010` and `T011` can be drafted in parallel after WP02.  
Risks: docs implying broader scope than ingest, systemd sandbox blocking writes, public docs exposing internal deployment assumptions, or accidentally committing secrets.

## Requirement Mapping

- WP01 maps FR-006, FR-007, FR-008, FR-009, FR-010, FR-012
- WP02 maps FR-001, FR-002, FR-003, FR-004, FR-005, FR-010, FR-011, FR-012
- WP03 maps FR-013, FR-014

## Final Verification

Before the mission is complete:

- [ ] `python3 -m compileall meter_cam_ingest` passes
- [ ] `pytest -q` passes
- [ ] local `/health` curl returns JSON 200
- [ ] local valid upload curl returns JSON 201
- [ ] smoke upload creates JPEG and `latest.json` under the configured temporary root
- [ ] git diff/status inspection finds no committed secrets, absolute local machine paths, or unprofessional/internal-deployment wording in public-facing files
