# Changelog

## Unreleased

### Changed

- Documented Holm correction as step-down monotonic adjustment with original-order output (`docs/specs/L3-validation.md`).
- Documented Tier-A memory append concurrency guarantees (per-file in-process locking) and strict `entity_id` constraints (`docs/specs/L4-memory.md`).
- Documented memory search API `limit >= 1` validation and error behavior (`docs/specs/L4-memory.md`).
- Added engine runtime spec covering session recording file-existence checks plus daemon ingestion and graceful shutdown semantics (`docs/specs/L3-engine.md`).
- Added caller migration note for API/runtime behavior changes (`docs/migrations/2026-02-20-api-behavior-changes.md`).
