---
work_package_id: WP03
title: Docs deploy and smoke verification
dependencies:
- WP02
requirement_refs:
- FR-013
- FR-014
tracker_refs: []
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
phase: Phase 3 - Handoff
agent: ''
history:
- timestamp: '2026-07-05T17:08:00Z'
  agent: hermes
  action: Prompt generated via Spec Kitty tasks planning
agent_profile: python-pedro
authoritative_surface: deploy/
create_intent:
- deploy/meter-cam-ingest.service
- deploy/meter-cam-ingest.env.example
- README.md
execution_mode: code_change
owned_files:
- deploy/meter-cam-ingest.service
- deploy/meter-cam-ingest.env.example
- README.md
role: implementer
tags: []
---

# Work Package Prompt: WP03 – Docs deploy and smoke verification

## ⚡ Do This First: Load Agent Profile

Load the Python implementation profile before changing files. If using Spec Kitty agent surfaces, run the assigned profile-loading step for `python-pedro`; otherwise follow strict verification discipline manually.

## Objective

Add deployment samples and operator documentation, then prove the completed service works with a real local background process and curl upload.

## Context

WP03 is not allowed to expand service scope. It documents deployment and handoff only. The service remains a narrow-scoped ingest boundary: no LLM, no email, no Telegram, no n8n, no S3.

## Requirements Covered

FR-013, FR-014, NFR-003, NFR-004

## Detailed Guidance

### T010 — Add deployment samples

Create:

- `deploy/meter-cam-ingest.service`
- `deploy/meter-cam-ingest.env.example`

The systemd unit should:

- run as `metercam`
- load `/etc/meter-cam-ingest.env`
- set `PYTHONDONTWRITEBYTECODE=1`
- use `/opt/meter-cam-ingest` as working directory
- restrict writes to `/srv/meter-cam`

The env example must use placeholders for secrets.

### T011 — Add README

Document:

- what the service does
- what it explicitly does not do
- config vars
- API examples
- storage layout
- local run command
- curl upload test
- downstream automation handoff expectations
- production deployment notes suitable for a public GitHub repository

Do not include repository access credential guidance, personal usernames, absolute local machine paths, informal wording, or redacted/broken command fragments.

### T012 — Run local smoke test

Run the completed service in the background with a temporary storage root and test API key. Verify:

- `/health` returns JSON 200
- valid upload returns JSON 201
- JPEG and `latest.json` exist under the temp root

### T013 — Inspect and commit

Before committing:

- Run `pytest -q`.
- Run `python3 -m compileall meter_cam_ingest`.
- Inspect git status/diff for secrets.
- Commit the completed artifacts.

## Definition of Done

- Deploy samples exist and use placeholders only.
- README captures the ingest-only boundary clearly with professional public-repository wording.
- Local curl smoke test has actually run successfully.
- No secrets are committed.

## Risks for Reviewer

- Check docs do not imply this service sends email or Telegram.
- Check docs and committed tool metadata do not contain internal deployment caveats, personal usernames, absolute local machine paths, informal wording, or malformed redacted examples.
- Check env example does not include real tokens.
- Check systemd sandbox still allows writes to `/srv/meter-cam`.
