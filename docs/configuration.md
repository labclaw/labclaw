# Configuration Reference

LabClaw is configured via YAML files. The default configuration is at
`configs/default.yaml`. Override with a custom file:

```bash
labclaw serve --config configs/production.yaml
```

---

## Default Configuration

```yaml
system:
  name: labclaw
  version: 0.0.2
  log_level: INFO

graph:
  backend: sqlite
  path: data/labclaw.db

events:
  backend: memory
  redis_url: redis://localhost:6379

api:
  host: 0.0.0.0
  port: 8000

edge:
  watch_paths: []
  poll_interval_seconds: 5

llm:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key_env: ANTHROPIC_API_KEY
  temperature: 0.7
  max_tokens: 2048
  fallback_provider: local

agents:
  default_model: claude-sonnet-4-6
  max_tool_calls: 20
```

---

## Section Reference

### system

General system settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `name` | string | `"labclaw"` | Instance name |
| `version` | string | `"0.0.1"` | Configuration version |
| `log_level` | string | `"INFO"` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### graph

Knowledge graph backend settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `backend` | string | `"sqlite"` | Graph storage backend |
| `path` | string | `"data/labclaw.db"` | Path to SQLite database file |

### events

Event bus configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `backend` | string | `"memory"` | Event bus backend: `memory` (in-process) or `redis` |
| `redis_url` | string | `"redis://localhost:6379"` | Redis connection URL (only used when backend is `redis`) |

Use `memory` for single-node deployments. Use `redis` when multiple processes
or nodes need to share events.

### api

REST API server settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `host` | string | `"0.0.0.0"` | Bind address |
| `port` | int | `8000` | Listen port |

Note: The daemon uses `--port` (default 18800), which overrides this value.

### edge

Edge file watcher settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `watch_paths` | list of strings | `[]` | Directories to monitor for new data files |
| `poll_interval_seconds` | int | `5` | Polling interval for file system checks |

### llm

LLM provider configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `provider` | string | `"anthropic"` | Provider name: `anthropic`, `openai`, or `local` |
| `model` | string | `"claude-sonnet-4-6"` | Model identifier |
| `api_key_env` | string | `"ANTHROPIC_API_KEY"` | Environment variable containing the API key |
| `temperature` | float | `0.7` | Sampling temperature |
| `max_tokens` | int | `2048` | Maximum tokens per completion |
| `fallback_provider` | string | `"local"` | Fallback if primary provider fails (or `null` for none) |

Supported providers:

| Provider | `api_key_env` | Models |
|----------|--------------|--------|
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6`, `claude-haiku-4` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o`, `gpt-4o-mini` |
| `local` | (none) | Template-based fallback (no API needed) |

### agents

Agent runtime settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_model` | string | `"claude-sonnet-4-6"` | Default LLM model for agents |
| `max_tool_calls` | int | `20` | Maximum tool calls per agent conversation turn |

---

## Daemon Command-Line Options

The daemon (`labclaw serve`) accepts these flags, which override config file values:

| Flag | Default | Description |
|------|---------|-------------|
| `--data-dir PATH` | `/opt/labclaw/data` | Directory to watch for new data files |
| `--memory-root PATH` | `/opt/labclaw/memory` | Root directory for Tier A memory |
| `--port PORT` | `18800` | REST API server port |
| `--dashboard-port PORT` | `18801` | Streamlit dashboard port |
| `--discovery-interval SEC` | `300` | Seconds between discovery runs |
| `--evolution-interval SEC` | `1800` | Seconds between evolution runs |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes (if using Anthropic) | Anthropic API key |
| `OPENAI_API_KEY` | Yes (if using OpenAI) | OpenAI API key |

---

## Example Configurations

### Minimal (demo, no API keys)

```yaml
system:
  name: demo
  log_level: INFO

llm:
  provider: local
  model: template
  api_key_env: ""
```

### Development

```yaml
system:
  name: dev
  log_level: DEBUG

llm:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key_env: ANTHROPIC_API_KEY

edge:
  watch_paths:
    - ./data
  poll_interval_seconds: 2
```

### Production

```yaml
system:
  name: labclaw
  log_level: WARNING

graph:
  backend: sqlite
  path: /opt/labclaw/data/labclaw.db

events:
  backend: redis
  redis_url: redis://localhost:6379

llm:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key_env: ANTHROPIC_API_KEY
  temperature: 0.5
  max_tokens: 4096

edge:
  watch_paths:
    - /data/rig-1
    - /data/rig-2
    - /data/microscope
  poll_interval_seconds: 10
```
