# Migration Note: 2026-02-20 API and Runtime Behavior Changes

This note documents caller-visible behavior updates that may require client changes.

## 1) Memory entity ID validation is strict at API boundary

Affected endpoints:

- `GET /api/memory/{entity_id}/soul`
- `GET /api/memory/{entity_id}/memory`
- `POST /api/memory/{entity_id}/memory`

New behavior:

- `entity_id` must match `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`.
- Invalid IDs now return `400`.

Caller impact:

- Clients that previously sent IDs with `/`, `*`, empty strings, or traversal-like values must sanitize before calling.

## 2) Memory search `limit` now validated

Affected endpoint:

- `GET /api/memory/search/query`

New behavior:

- `limit` must be `>= 1`.
- Invalid values (for example `limit=0`) return `422` validation errors.

Caller impact:

- Add client-side bounds checks or handle `422` responses.

## 3) Session recording now requires an existing file

Affected endpoint:

- `POST /api/sessions/{session_id}/recordings`

New behavior:

- `file_path` must resolve under `LABCLAW_DATA_DIR`.
- `file_path` must already exist and be a file.
- Missing files return `400` with `"Recording file does not exist"`.

Caller impact:

- Upload/write/sync the recording first, then call the recordings endpoint.

## 4) Daemon ingestion and shutdown are more defensive

Runtime behavior updates:

- Ingestion retries are allowed when a detected file has zero parsed rows (file is not marked processed yet).
- `hardware.file.detected` without `path` is ignored with a warning instead of crashing ingestion.
- Shutdown escalates dashboard stop (`terminate` -> `kill` on timeout), closes log handles, and clears process references.

Caller impact:

- Event producers should always include `payload.path` for `hardware.file.detected`.
- Operators should expect cleaner daemon teardown when dashboard subprocesses are slow to exit.

## Recommended Caller Checklist

1. Validate memory `entity_id` format before request dispatch.
2. Ensure memory search `limit >= 1`.
3. Ensure session recording files exist on disk before POSTing recordings.
4. Include `path` in all `hardware.file.detected` events.
