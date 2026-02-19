---
name: build-and-test
description: "Build the Jarvis Mesh project and run the full test suite, reporting results with pass/fail counts and any errors."
user-invocable: true
allowed-tools: Bash, Read, Grep
context: fork
---

You are running the build and test pipeline for Jarvis Mesh.

## Steps

1. Check Python version:
```bash
python3 --version
```

2. Install the project in development mode (if not already installed):
```bash
pip install -e ".[dev]" 2>&1 | tail -5
```

3. Run linting:
```bash
ruff check src/ tests/ --output-format=concise 2>&1
```

4. Run type checking (if mypy is configured):
```bash
mypy src/jarvis_mesh/ --ignore-missing-imports 2>&1 | tail -20
```

5. Run the test suite:
```bash
pytest tests/ -v --tb=short 2>&1
```

6. Report results:
- Number of tests passed/failed/skipped
- Any lint errors
- Any type errors
- Summary recommendation (ready to commit / needs fixes)
