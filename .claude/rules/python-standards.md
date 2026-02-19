# Python Coding Standards — Jarvis Mesh

## Language & Runtime
- Python 3.11+ required
- Use `from __future__ import annotations` for forward references
- Prefer `pathlib.Path` over `os.path` for all file operations

## Type Hints
- Required on all public function signatures (parameters + return type)
- Use `collections.abc` types (`Sequence`, `Mapping`) over `typing` equivalents
- Use `X | None` syntax instead of `Optional[X]`

## Data Models
- All data schemas use Pydantic `BaseModel`
- Graph node types extend a common `GraphNode` base
- Event types extend a common `LabEvent` base
- Validate at boundaries (API input, file parsing), trust internally

## Error Handling
- Never silently catch exceptions — log or re-raise
- Use specific exception types, not bare `except`
- Device/network operations: retry with exponential backoff, then fail loudly

## Testing
- `pytest` with `pytest-asyncio` for async tests
- Test files mirror source structure: `tests/unit/core/test_graph.py` for `src/jarvis_mesh/core/graph.py`
- Fixtures in `tests/fixtures/` for sample data files

## Imports
- Sort with `ruff` (isort-compatible)
- Standard library → third-party → local, separated by blank lines

## JSON Serialization
- Always cast numpy `int64`/`float64` with `int()` / `float()` before `json.dumps()`
- Timestamps in ISO 8601 format
- File output names with `YYYYMMDD_HHMMSS` suffix
