# L3 Engine Runtime Spec

**Layer:** Engine Runtime (L3)
**Design doc reference:** Section 5.1 (Session Chronicle)

## Purpose

Defines runtime behavior for session assembly and continuous daemon execution:

- Session Chronicle lifecycle (`start_session`, `add_recording`, `end_session`)
- File-ingestion behavior used by the daemon
- Graceful shutdown semantics

---

## Session Chronicle Contracts

### Session capacity eviction

- `SessionChronicle(max_sessions=N)` evicts one session before creating a new one when capacity is reached.
- Eviction preference:
  - First, oldest completed session (`duration_seconds is not None`)
  - Otherwise, oldest session by `session_date`

### Recording creation

- `SessionChronicle.add_recording()` requires an existing `session_id`; missing session raises `KeyError`.
- API boundary (`POST /api/sessions/{session_id}/recordings`) enforces:
  - `file_path` must resolve inside `LABCLAW_DATA_DIR`
  - `file_path` must exist as a file (`is_file()`)
- API failures:
  - Path outside data dir -> `400` (`"Path outside data directory"`)
  - Missing file -> `400` (`"Recording file does not exist"`)

---

## Daemon Ingestion Semantics

### DataAccumulator

- Supported file extensions: `.csv`, `.tsv`, `.txt` only.
- Uses thread-safe tracking sets:
  - `_files_in_progress`: prevents duplicate concurrent ingestion of same path
  - `_files_processed`: marks completed ingests
- A path is marked processed only after at least one parsed row is ingested.
- If parsing yields zero rows or ingestion fails, the file is not marked processed, so later retries can succeed.
- `_files_in_progress` is always cleared in `finally`, including failures.

### Event-driven ingestion

- Daemon subscribes to `hardware.file.detected`.
- Event payload must include `path`; missing `path` is logged and ignored.
- `FileDetectedHandler` emits events for both `created` and `modified` file changes (`change_type` in payload), enabling late-write ingestion retries.

---

## Graceful Shutdown Semantics

`LabClawDaemon.stop()` guarantees:

- Set global stop event for discovery/evolution loops.
- Stop all watcher observers.
- Stop dashboard subprocess with escalation:
  - `terminate()` + wait up to 5s
  - If timeout: `kill()` + wait up to 5s
  - Log warning/error if process still fails to exit
- Always clear `_dashboard_proc` and close/reset `_dashboard_log`.
- Append a final `daemon_stop` memory entry with summary counters.

