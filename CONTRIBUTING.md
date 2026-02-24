# Contributing

Thanks for contributing to LabClaw.

## Development Setup

```bash
uv sync --extra dev --extra science
```

## Run Tests

```bash
uv run --extra dev --extra science pytest -q
```

## Style

```bash
uv run --extra dev ruff check src tests
```

## Pull Requests

- Keep PRs focused and small.
- Include tests for behavior changes.
- Update docs (`README.md`, specs, or roadmap) when behavior changes.
- Use clear PR titles: `module: short summary`.
- Ensure CI is green (`lint`, `test`, `package` jobs).

## Good First Contributions

- Add tests for uncovered edge cases.
- Improve error messages and API docs.
- Add examples for new lab modalities.
