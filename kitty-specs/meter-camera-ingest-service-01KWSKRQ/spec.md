# Feature Specification: Meter Camera Ingest Service

**Mission**: `meter-camera-ingest-service-01KWSKRQ`  
**Project**: `meter-cam-ingest`  
**Status**: Draft for implementation  
**Target branch**: `main`  
**Created**: 2026-07-05

## Summary

Build a small, narrow-scoped LAN-only image ingest service for a monthly water-meter camera. The service accepts a token-authenticated raw JPEG upload from the camera, stores the original image durably under `/srv/meter-cam`, writes metadata for the newest successful upload, and exposes a health endpoint.

The service is only the capture handoff boundary. Downstream automation performs every workflow/business step after ingest: missing-photo alerts, LLM extraction, second-LLM verification, non-decreasing reading checks, email draft creation, approval, and email sending.

## Goals

- Provide a stable HTTP target for an ESPHome/M5Stack camera to upload one monthly JPEG.
- Persist every valid upload immutably, allowing retries without losing evidence.
- Maintain a simple `latest.json` pointer for downstream automation to consume.
- Avoid operational weight: no database, no queue, no object storage, no web framework runtime dependency.
- Make deployment easy as a systemd service on a Linux host.
- Keep all specs and implementation artifacts in the app repository.

## Non-Goals

- Do not call LLMs.
- Do not send email.
- Do not send Telegram messages.
- Do not run n8n workflows.
- Do not upload to S3/MinIO.
- Do not implement meter-reading extraction or verification.
- Do not own approval state.
- Do not expose a public internet API for MVP.
- Do not modify ESPHome YAML in this mission.
- Do not create the downstream scheduled workflow in this mission.

## Context and Decisions

The full pipeline target is:

1. Camera takes a photo once a month on the 28th, around midnight Europe/Warsaw.
2. Image reaches Hermes-accessible storage.
3. Hermes sends the image to an LLM for meter reading extraction.
4. A second LLM verifies the extraction.
5. Hermes compares values against the previous approved month; values must never decrease.
6. Hermes prepares a plain-text email with meter values.
7. Hermes requests approval via Telegram and sends the email only after approval.

This mission implements only step 2: camera-to-filesystem ingest.

Rejected MVP alternatives:

- Direct camera-to-Hermes webhook: Hermes webhooks are JSON/prompt-oriented and not ideal for raw JPEG payloads.
- Direct camera-to-S3/MinIO: adds signing/credentials complexity and still needs local state/processing.
- n8n as workflow/state machine: adds avoidable operational complexity for one monthly image.
- Database-backed ingest service: unnecessary for one camera/month; atomic files are easier to inspect and back up.

## Actors

- **Camera device**: ESPHome/M5Stack-style camera posting JPEG bytes.
- **Ingest service**: this app, running as `metercam` on the deployment host.
- **Downstream automation**: scheduled reader of stored files and metadata.
- **Operator**: person who deploys/configures the service and handles later approval steps.

## Functional Requirements

| ID | Title | Description | Priority | Status |
| --- | --- | --- | --- | --- |
| FR-001 | Health endpoint | The service exposes a JSON health endpoint so deployment automation and operators can confirm the ingest process is running. | High | Accepted |
| FR-002 | JPEG capture endpoint | The camera can submit raw JPEG bytes for the water meter and receive durable storage metadata on success. | High | Accepted |
| FR-003 | Token authentication | Capture uploads require the configured API key and never expose the secret in responses or logs. | High | Accepted |
| FR-004 | Device allowlist | Deployments can restrict accepted camera device IDs and reject unknown devices. | Medium | Accepted |
| FR-005 | Upload validation | Invalid methods, paths, lengths, media types, sizes, and non-JPEG bodies receive deterministic JSON errors. | High | Accepted |
| FR-006 | Monthly storage layout | Valid uploads are stored under the configured root by meter ID and Europe/Warsaw month. | High | Accepted |
| FR-007 | Atomic persistence | Image bytes and latest metadata are written atomically so Hermes never reads partial handoff state. | High | Accepted |
| FR-008 | Duplicate upload handling | Multiple uploads in one month are preserved and the newest success becomes the latest pointer. | High | Accepted |
| FR-009 | Timezone-aware month calculation | Month keys are computed in the configured timezone, defaulting to Europe/Warsaw. | High | Accepted |
| FR-010 | Environment configuration | Runtime host, port, storage root, API key, timezone, size limits, and allowed devices are configured from environment variables. | High | Accepted |
| FR-011 | JSON response contract | Every success and error response is JSON with stable fields for automation and debugging. | Medium | Accepted |
| FR-012 | Handoff metadata | The latest metadata file contains the image path and enough upload facts for downstream automation to process the current month. | High | Accepted |
| FR-013 | Deployment samples | The repo includes systemd and environment examples suitable for Linux deployment. | Medium | Accepted |
| FR-014 | Public operator documentation | The README documents boundaries, configuration, local usage, API examples, storage, and downstream handoff in a professional form suitable for a public GitHub repository. | Medium | Accepted |

### FR-001 Health endpoint

The service MUST expose `GET /health`.

Success response:

```json
{"ok": true, "service": "meter-cam-ingest"}
```

- Status: `200 OK`
- Content-Type: `application/json`

### FR-002 JPEG capture endpoint

The service MUST expose `POST /capture/water`.

Required headers:

```text
Content-Type: image/jpeg
X-Api-Key: <upload-api-key>
X-Device-Id: m5stack-timercam-water
```

Body:

- Raw JPEG bytes, not multipart form data.

On success, return `201 Created` with JSON metadata containing at least:

- `ok: true`
- `meter_id: "water"`
- `month`, e.g. `2026-06`
- `sha256`
- `bytes`
- `image_path`
- `latest_meta_path`

### FR-003 Authentication

The capture endpoint MUST reject missing or invalid `X-Api-Key` values with `401 Unauthorized`.

- Token comparison MUST use constant-time comparison.
- Token values MUST NOT be logged or returned.
- `/health` does not require auth.

### FR-004 Device allowlist

When `METER_CAM_ALLOWED_DEVICE_IDS` is configured, the capture endpoint MUST reject any `X-Device-Id` not in the allowlist.

- Rejection status: `403 Forbidden`
- Allowed default: `m5stack-timercam-water`

### FR-005 Content validation

The capture endpoint MUST reject invalid uploads:

- Wrong method: `405 Method Not Allowed`
- Unknown path: `404 Not Found`
- Missing `Content-Length`: `411 Length Required`
- Invalid `Content-Length`: `400 Bad Request`
- Body larger than configured max: `413 Payload Too Large`
- Body smaller than configured min: `400 Bad Request`
- Media type other than `image/jpeg`: `415 Unsupported Media Type`
- Body that does not begin with JPEG magic bytes `0xFF 0xD8`: `400 Bad Request`

The service SHOULD accept `image/jpeg` with optional parameters, e.g. `image/jpeg; charset=binary`, by parsing only the media type.

### FR-006 Storage layout

Valid uploads MUST be stored under:

```text
<root>/captures/water/<YYYY-MM>/
```

Default root:

```text
/srv/meter-cam
```

Each image filename MUST include:

- a timezone-aware capture timestamp safe for filenames
- enough SHA-256 prefix to identify content
- collision handling so rapid duplicate uploads cannot overwrite or corrupt an existing image

Example:

```text
2026-06-28T00-01-04.123456+02-00__a1b2c3d4e5f6.jpg
```

### FR-007 Atomic writes

For every valid upload, the service MUST:

1. Create the month directory if missing.
2. Write image bytes to a temporary file in that directory.
3. fsync the image file.
4. Atomically rename the temp file to the final image path.
5. Write `latest.json.tmp` with metadata.
6. fsync metadata.
7. Atomically rename `latest.json.tmp` to `latest.json`.

The service MUST NOT update `latest.json` until the image is safely stored.

### FR-008 Duplicate uploads

Multiple successful uploads in the same month MUST be allowed.

- Each successful upload gets its own immutable image file.
- `latest.json` points to the newest successful upload.
- Older images remain available for audit/recovery.

### FR-009 Timezone/month calculation

The service MUST compute `month` using the configured timezone, default `Europe/Warsaw`.

The service MUST NOT depend on UTC month boundaries for capture organization.

### FR-010 Runtime configuration

The service MUST be configurable via environment variables:

```bash
METER_CAM_BIND_HOST=0.0.0.0
METER_CAM_PORT=8097
METER_CAM_ROOT=/srv/meter-cam
METER_CAM_API_KEY=<secret>
METER_CAM_TZ=Europe/Warsaw
METER_CAM_MAX_BYTES=5242880
METER_CAM_MIN_BYTES=2048
METER_CAM_ALLOWED_DEVICE_IDS=m5stack-timercam-water
```

`METER_CAM_API_KEY` is required for serving capture uploads.

### FR-011 Response format

All API responses MUST be JSON.

Error responses MUST contain:

```json
{"ok": false, "error": "stable-machine-readable-code", "message": "human readable message"}
```

Messages MUST NOT include secrets.

### FR-012 Downstream handoff contract

Downstream automation consumes:

```text
/srv/meter-cam/captures/water/<YYYY-MM>/latest.json
```

`latest.json` MUST include at least:

```json
{
  "ok": true,
  "meter_id": "water",
  "device_id": "m5stack-timercam-water",
  "month": "2026-06",
  "received_at": "2026-06-28T00:01:04.123456+02:00",
  "sha256": "...",
  "bytes": 348123,
  "image_path": "/srv/meter-cam/captures/water/2026-06/...jpg"
}
```

The ingest service does not create downstream workflow files, except by documenting the expected handoff.

### FR-013 Systemd deployment sample

The repository MUST include deployment sample files:

- `deploy/meter-cam-ingest.service`
- `deploy/meter-cam-ingest.env.example`

The systemd sample MUST run as `metercam`, set `PYTHONDONTWRITEBYTECODE=1`, use `/etc/meter-cam-ingest.env`, and restrict writes to `/srv/meter-cam`.

### FR-014 Public operator documentation

The repository MUST include a README documenting:

- service boundaries: what it does and explicitly does not do
- local run instructions
- configuration variables
- API examples
- storage layout
- curl upload test
- downstream automation handoff expectations
- deployment notes

The README and deployment examples MUST be suitable for a public GitHub repository:

- no real credentials, hostnames, personal usernames, or internal deployment assumptions
- no repository access credential guidance for this public project
- no informal wording in public-facing documentation
- examples must use clear placeholders or environment-variable references rather than redacted or malformed command fragments

## Non-Functional Requirements

### NFR-001 Runtime dependency minimalism

Production runtime MUST use only Python standard library modules.

Test dependencies MAY include pytest, but production must not require pytest, FastAPI, uvicorn, requests, or any other third-party library.

### NFR-002 File safety

The service MUST use atomic writes for image and metadata files.

The service MUST avoid overwriting existing image files, even under rapid retry or duplicate upload conditions.

### NFR-003 Security posture

The MVP is LAN-only token-authenticated HTTP.

- Do not expose publicly for MVP.
- Do not log secrets.
- Do not commit secrets.
- Keep public documentation and committed tool metadata free of real credentials, personal usernames, absolute local machine paths, repository access credential guidance, and malformed redacted examples.
- If public exposure is added later, require TLS/reverse proxy and revisit auth/rate-limiting.

### NFR-004 Observability

The service SHOULD print simple structured-ish logs to stdout/stderr suitable for `journalctl`.

Logs SHOULD include success/failure class, path, byte count, device ID, month, and image path where applicable. Logs MUST NOT include API key values.

### NFR-005 Testability

Storage and server behavior MUST be covered by automated tests.

At minimum tests must cover:

- month calculation in Europe/Warsaw
- atomic storage creates image + latest metadata
- duplicate uploads preserve multiple images
- health endpoint
- auth failures
- device allowlist failures
- content-type failures
- size failures
- missing/invalid content-length
- non-JPEG body rejection
- successful upload writes expected files

### NFR-006 Compatibility

The service SHOULD run on Debian/Linux with Python 3.11+.

## Acceptance Criteria

- `python3 -m compileall meter_cam_ingest` succeeds.
- Automated tests pass locally.
- Running the module starts an HTTP service from environment config.
- `GET /health` returns `200` with JSON body.
- Valid JPEG `POST /capture/water` returns `201` and writes both an immutable JPEG and `latest.json`.
- Invalid token/content/device/body cases return the specified error statuses and JSON bodies.
- Duplicate rapid uploads do not overwrite an existing image.
- No committed file contains an upload API key or GitHub token.
- README and deploy samples are present, professional, public-repository-safe, and contain only placeholders for credentials.
- Spec Kitty artifacts are committed with the app source.

## Out-of-Scope Downstream State

The following state files are documented for the larger pipeline but not created or modified by this app during normal upload handling:

```text
/srv/meter-cam/state/latest-approved.json
/srv/meter-cam/state/readings.jsonl
/srv/meter-cam/workflow/water/<YYYY-MM>/status.json
/srv/meter-cam/workflow/water/<YYYY-MM>/extraction.json
/srv/meter-cam/workflow/water/<YYYY-MM>/verification.json
/srv/meter-cam/workflow/water/<YYYY-MM>/email-draft.txt
```

Initial downstream baseline, to be seeded by deployment/Hermes workflow if needed:

```json
{"month":"2026-05","domowy":128.675,"ogrodowy":9.455}
```

## Open Questions for Deployment, Not Implementation

- Exact deployment inventory host/group.
- Exact downstream automation runtime user/group that needs read access to stored captures.
- Whether port `8097` is acceptable in production.
- Whether firewall allowlist is added in the first deployment or deferred.
