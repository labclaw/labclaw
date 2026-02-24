# CI/CD Reference

This repository uses GitHub Actions for CI, security scanning, release
automation, and deployment.

## Workflows

- `ci.yml`
  - Triggers: push/pull_request on `main`, manual dispatch
  - Jobs:
    - `lint`: `ruff` error-focused checks (`E,F,I,W`)
    - `compatibility (py3.11)`: unit test compatibility sweep
    - `test`: full test suite with `dev+science` extras
    - `package`: build wheel/sdist and run `twine check`
- `security.yml`
  - Triggers: push/pull_request on `main`, weekly schedule, manual dispatch
  - Jobs:
    - `dependency-audit`: `pip-audit`
    - `codeql`: static analysis (non-PR events)
- `release.yml`
  - Triggers: `v*` tags, manual dispatch with a tag
  - Jobs:
    - Build artifacts
    - Publish GitHub Release
    - Optional PyPI publish when `PYPI_API_TOKEN` is configured
- `deploy.yml`
  - Trigger: manual dispatch
  - Syncs code, installs dependencies on remote host, restarts systemd service,
    and optionally runs smoke checks.

## Branch Protection

Recommended required status checks for `main`:

- `lint`
- `test`
- `package`

Also require:

- Pull request reviews (`>=1`)
- Conversation resolution
- Linear history
- No force-pushes
- No branch deletion

## Secrets and Variables

### Release

- `PYPI_API_TOKEN` (optional): enables PyPI publishing in `release.yml`

### Deploy

Required secrets:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_PRIVATE_KEY`

Optional secret:

- `DEPLOY_SSH_PORT` (defaults to `22`)

Optional repository variables:

- `DEPLOY_REMOTE_DIR` (default `/opt/labclaw`)
- `DEPLOY_SERVICE_NAME` (default `labclaw`)

## Operational Notes

- The deploy workflow currently expects a root-capable deploy user because it
  provisions users and writes systemd units.
- `pip-audit` may show local package names (`labclaw`) as non-PyPI packages;
  this is expected and non-blocking.
