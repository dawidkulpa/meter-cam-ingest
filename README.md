# meter-cam-ingest

Small LAN-only JPEG ingest service for a monthly water-meter camera.

The service has a narrow responsibility: accept a token-authenticated raw JPEG upload, store the original image under a month directory, and write `latest.json` metadata for downstream automation.

## Scope

This service handles capture ingest only. It does not:

- call LLMs
- read meter values
- verify meter values
- send Telegram messages
- send email
- run n8n workflows
- upload to S3/MinIO
- own approval state

Downstream automation can consume the stored image and metadata to perform extraction, verification, approval, and submission.

## Runtime requirements

- Python 3.11+
- Linux/systemd for the production deployment sample
- No third-party runtime dependencies

Tests use pytest.

## Configuration

Environment variables:

```bash
METER_CAM_BIND_HOST=0.0.0.0
METER_CAM_PORT=8097
METER_CAM_ROOT=/srv/meter-cam
METER_CAM_API_KEY=<upload-api-key>
METER_CAM_TZ=Europe/Warsaw
METER_CAM_MAX_BYTES=5242880
METER_CAM_MIN_BYTES=2048
METER_CAM_ALLOWED_DEVICE_IDS=m5stack-timercam-water
```

`METER_CAM_API_KEY` is required for capture uploads. Keep the real value in the deployment environment, not in source control.

## API

### Health

```bash
curl -s http://127.0.0.1:8097/health
```

Expected response:

```json
{"ok": true, "service": "meter-cam-ingest"}
```

### Upload capture

```bash
curl -i \
  -X POST \
  -H "Content-Type: image/jpeg" \
  -H "X-Api-Key: ${METER_CAM_API_KEY}" \
  -H "X-Device-Id: m5stack-timercam-water" \
  --data-binary @tests/fixtures/tiny.jpg \
  http://127.0.0.1:8097/capture/water
```

Success response status: `201 Created`.

Response body includes:

```json
{
  "ok": true,
  "meter_id": "water",
  "device_id": "m5stack-timercam-water",
  "month": "2026-06",
  "received_at": "2026-06-28T00:01:04.123456+02:00",
  "sha256": "...",
  "bytes": 348123,
  "image_path": "/srv/meter-cam/captures/water/2026-06/...jpg",
  "latest_meta_path": "/srv/meter-cam/captures/water/2026-06/latest.json"
}
```

All errors are JSON:

```json
{"ok": false, "error": "stable-code", "message": "human readable message"}
```

Common statuses:

- `401` missing/invalid API key
- `403` device ID not allowed
- `411` missing Content-Length
- `413` body too large
- `415` unsupported media type
- `400` invalid size/content/JPEG body
- `404` unknown path
- `405` unsupported method

## Storage layout

Default root: `/srv/meter-cam`

```text
/srv/meter-cam/
  captures/
    water/
      2026-06/
        2026-06-28T00-01-04.123456+02-00__a1b2c3d4e5f6abcd.jpg
        latest.json
```

Multiple uploads in one month are allowed. Each successful upload gets its own immutable JPEG. `latest.json` points to the newest successful upload.

Downstream automation should read:

```text
/srv/meter-cam/captures/water/<YYYY-MM>/latest.json
```

If that file is missing when the monthly workflow runs, downstream automation should notify the operator that the current-month capture has not arrived.

## Local development

Run tests:

```bash
python3 -m compileall meter_cam_ingest
pytest -q
```

Run locally:

```bash
export METER_CAM_BIND_HOST=127.0.0.1
export METER_CAM_PORT=8097
export METER_CAM_ROOT=/tmp/meter-cam-dev
export METER_CAM_API_KEY=local-upload-token
export METER_CAM_TZ=Europe/Warsaw
export METER_CAM_MAX_BYTES=5242880
export METER_CAM_MIN_BYTES=10
export METER_CAM_ALLOWED_DEVICE_IDS=m5stack-timercam-water
python3 -m meter_cam_ingest.server
```

In another shell:

```bash
curl -s http://127.0.0.1:8097/health
curl -i \
  -X POST \
  -H "Content-Type: image/jpeg" \
  -H "X-Api-Key: ${METER_CAM_API_KEY}" \
  -H "X-Device-Id: m5stack-timercam-water" \
  --data-binary @tests/fixtures/tiny.jpg \
  http://127.0.0.1:8097/capture/water
find /tmp/meter-cam-dev -maxdepth 5 -type f
```

## Production deployment sample

Sample files are in `deploy/`:

- `deploy/meter-cam-ingest.service`
- `deploy/meter-cam-ingest.env.example`

Expected production paths:

```text
/opt/meter-cam-ingest
/etc/meter-cam-ingest.env
/srv/meter-cam
```

Recommended service user/group:

```text
metercam:metercam
```

The downstream automation user must be able to read `/srv/meter-cam/captures/.../latest.json` and the referenced image. A typical deployment grants read access by adding that user to the `metercam` group.

## Spec Kitty artifacts

This repo was initialized with Spec Kitty. The ingest-service mission lives under:

```text
kitty-specs/meter-camera-ingest-service-01KWSKRQ/
```

The spec, plan, tasks, work-package prompts, lanes, and acceptance matrix are committed with the app source.
