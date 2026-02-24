# API Reference

LabClaw exposes a REST API via FastAPI on port 18800 (default). Interactive Swagger UI
is available at `http://localhost:18800/docs` when the server is running.

Base URL: `http://localhost:18800`

---

## Health

### GET /api/health

Returns basic liveness probe.

**Response:**

```json
{"status": "ok", "version": "0.0.2"}
```

**Example:**

```bash
curl http://localhost:18800/api/health
```

### GET /api/status

Returns system status including registered events and devices.

**Response:**

```json
{
  "status": "ok",
  "version": "0.0.2",
  "registered_events": 42,
  "registered_devices": 3
}
```

**Example:**

```bash
curl http://localhost:18800/api/status
```

---

## Sessions

Manage experimental recording sessions. Each session groups related recordings.

Prefix: `/api/sessions`

### GET /api/sessions/

List all sessions.

**Response:** Array of `SessionNode` objects.

```bash
curl http://localhost:18800/api/sessions/
```

### GET /api/sessions/{session_id}

Get a single session by ID.

**Response:** `SessionNode` object.

**Errors:** 404 if session not found.

```bash
curl http://localhost:18800/api/sessions/abc123
```

### POST /api/sessions/

Start a new recording session.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `operator` | string | No | ID of the operator starting the session |
| `experiment_id` | string | No | Parent experiment ID |

**Response:** `SessionNode` (201 Created).

```bash
curl -X POST http://localhost:18800/api/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"operator": "alice", "experiment_id": "exp-001"}'
```

### POST /api/sessions/{session_id}/recordings

Add a recording file to a session.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_path` | string | Yes | Path to the recording file (must be inside data directory) |
| `modality` | string | Yes | Recording modality (e.g. "electrophysiology", "video") |
| `device_id` | string | No | ID of the device that produced the recording |

**Response:** `RecordingNode` (201 Created).

**Errors:** 400 if path is outside data directory or file does not exist; 404 if session not found.

```bash
curl -X POST http://localhost:18800/api/sessions/abc123/recordings \
  -H "Content-Type: application/json" \
  -d '{"file_path": "data/recording_001.csv", "modality": "electrophysiology"}'
```

### POST /api/sessions/{session_id}/end

End a session and mark it as complete.

**Response:** Updated `SessionNode`.

**Errors:** 404 if session not found.

```bash
curl -X POST http://localhost:18800/api/sessions/abc123/end
```

---

## Memory

Read and write Tier A markdown memory (SOUL.md and MEMORY.md files).

Prefix: `/api/memory`

### GET /api/memory/search/query

Search across all SOUL.md and MEMORY.md files.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | `""` | Search query text |
| `limit` | int | 10 | Maximum results (min 1) |

**Response:** Array of `SearchResult` objects with `entity_id`, `snippet`, `score`, and `source` fields.

```bash
curl "http://localhost:18800/api/memory/search/query?q=calcium+imaging&limit=5"
```

### GET /api/memory/{entity_id}/soul

Read an entity's SOUL.md file.

**Response:**

```json
{
  "path": "lab/my-entity/SOUL.md",
  "frontmatter": {"name": "...", "type": "..."},
  "content": "# My Entity\n\n..."
}
```

**Errors:** 400 if entity_id is invalid; 404 if SOUL.md not found.

```bash
curl http://localhost:18800/api/memory/lab/soul
```

### GET /api/memory/{entity_id}/memory

Read an entity's MEMORY.md file.

**Response:** Same shape as SOUL.md response.

**Errors:** 400 if entity_id is invalid; 404 if MEMORY.md not found.

```bash
curl http://localhost:18800/api/memory/lab/memory
```

### POST /api/memory/{entity_id}/memory

Append a timestamped entry to an entity's MEMORY.md.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | string | Yes | Entry category (e.g. "discovery", "failure") |
| `detail` | string | Yes | Entry content |

**Response:** `{"entity_id": "...", "category": "...", "status": "appended"}` (201 Created).

```bash
curl -X POST http://localhost:18800/api/memory/lab/memory \
  -H "Content-Type: application/json" \
  -d '{"category": "observation", "detail": "Mouse 12 showed increased grooming behavior."}'
```

---

## Discovery

Pattern mining and hypothesis generation.

Prefix: `/api/discovery`

### POST /api/discovery/mine

Run pattern mining on provided data rows.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `data` | array of objects | Yes | Tabular data rows (each row is a dict) |
| `config` | object | No | Mining config overrides (see below) |

`config` fields (all optional):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_sessions` | int | 10 | Minimum rows to start mining |
| `correlation_threshold` | float | 0.5 | Minimum absolute correlation to report |
| `anomaly_z_threshold` | float | 2.0 | Z-score threshold for anomaly detection |

**Response:** `MiningResult` with `patterns` array and `data_summary`.

```bash
curl -X POST http://localhost:18800/api/discovery/mine \
  -H "Content-Type: application/json" \
  -d '{
    "data": [
      {"firing_rate": 10.5, "speed": 30.2, "accuracy": 0.85},
      {"firing_rate": 25.1, "speed": 15.0, "accuracy": 0.92}
    ],
    "config": {"min_sessions": 2}
  }'
```

### POST /api/discovery/hypothesize

Generate hypotheses from discovered patterns.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `patterns` | array of PatternRecord | Yes | Patterns to generate hypotheses from |
| `context` | string | No | Domain context for hypothesis generation |
| `constraints` | array of strings | No | Constraints for hypothesis generation |

**Response:** Array of `HypothesisOutput` objects.

```bash
curl -X POST http://localhost:18800/api/discovery/hypothesize \
  -H "Content-Type: application/json" \
  -d '{
    "patterns": [
      {
        "pattern_type": "correlation",
        "description": "firing_rate and speed are negatively correlated",
        "confidence": 0.85,
        "evidence": {"col_a": "firing_rate", "col_b": "speed", "correlation": -0.72}
      }
    ]
  }'
```

---

## Evolution

Self-evolution fitness tracking and cycle management.

Prefix: `/api/evolution`

### GET /api/evolution/history

Get evolution cycle history.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `target` | string | No | Filter by evolution target (`analysis_params`, `prompts`, `routing`, `heuristics`, `strategy`) |

**Response:** Array of `EvolutionCycle` objects sorted by start time.

```bash
curl http://localhost:18800/api/evolution/history
curl "http://localhost:18800/api/evolution/history?target=analysis_params"
```

### POST /api/evolution/fitness

Record a fitness measurement for an evolution target.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | Yes | Evolution target |
| `metrics` | object | Yes | Metric name-value pairs (e.g. `{"pattern_count": 5.0}`) |
| `data_points` | int | No | Number of data points used for measurement |

**Response:** `FitnessScore` object.

```bash
curl -X POST http://localhost:18800/api/evolution/fitness \
  -H "Content-Type: application/json" \
  -d '{"target": "analysis_params", "metrics": {"pattern_count": 12.0, "coverage": 0.8}}'
```

### POST /api/evolution/cycle

Start a new evolution cycle. Automatically measures baseline fitness and proposes a candidate.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | Yes | Evolution target |
| `n_candidates` | int | No | Number of candidates to propose (default: 1) |

**Response:** `EvolutionCycle` object (201 Created).

**Errors:** 400 if no candidates available for the target.

```bash
curl -X POST http://localhost:18800/api/evolution/cycle \
  -H "Content-Type: application/json" \
  -d '{"target": "analysis_params"}'
```

---

## Devices

Register, query, and manage lab instruments.

Prefix: `/api/devices`

### GET /api/devices/

List all registered devices.

**Response:** Array of `DeviceRecord` objects.

```bash
curl http://localhost:18800/api/devices/
```

### GET /api/devices/{device_id}

Get a single device by ID.

**Response:** `DeviceRecord`.

**Errors:** 404 if not found.

```bash
curl http://localhost:18800/api/devices/dev-001
```

### POST /api/devices/

Register a new device.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Human-readable device name |
| `device_type` | string | Yes | Type (e.g. "camera", "electrode_array") |
| `model` | string | No | Model number |
| `manufacturer` | string | No | Manufacturer name |
| `location` | string | No | Physical location in the lab |

**Response:** `DeviceRecord` (201 Created).

**Errors:** 409 if device with same ID already exists.

```bash
curl -X POST http://localhost:18800/api/devices/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Rig-1 Camera", "device_type": "camera", "model": "Basler acA1920", "location": "Room 201"}'
```

### PATCH /api/devices/{device_id}/status

Update a device's status.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string | Yes | New status: `online`, `offline`, `in_use`, `error`, `maintenance` |

**Response:** `{"device_id": "...", "status": "online"}`.

**Errors:** 404 if not found.

```bash
curl -X PATCH http://localhost:18800/api/devices/dev-001/status \
  -H "Content-Type: application/json" \
  -d '{"status": "online"}'
```

### DELETE /api/devices/{device_id}

Unregister a device.

**Response:** `{"device_id": "...", "deleted": "true"}`.

**Errors:** 404 if not found.

```bash
curl -X DELETE http://localhost:18800/api/devices/dev-001
```

---

## Agents

Chat with built-in AI agents.

Prefix: `/api/agents`

### POST /api/agents/chat

Send a message to the Lab Assistant agent.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | User message |

**Response:**

```json
{"response": "Based on the mining results...", "agent": "lab-assistant"}
```

**Errors:** 503 if LLM provider is not configured.

```bash
curl -X POST http://localhost:18800/api/agents/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What patterns did you find today?"}'
```

### POST /api/agents/designer/chat

Send a message to the Experiment Designer agent.

**Request body:** Same as `/chat`.

**Response:**

```json
{"response": "I recommend running...", "agent": "experiment-designer"}
```

**Errors:** 503 if LLM provider is not configured.

```bash
curl -X POST http://localhost:18800/api/agents/designer/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What experiment should we run next?"}'
```

### GET /api/agents/tools

List all available agent tools.

**Response:** Array of tool descriptors:

```json
[
  {
    "name": "query_memory",
    "description": "Search lab memory for past findings, patterns, and conclusions.",
    "parameters": {"query": {"type": "string", "description": "Search query"}}
  }
]
```

```bash
curl http://localhost:18800/api/agents/tools
```

---

## Plugins

Query loaded plugins.

Prefix: `/api/plugins`

### GET /api/plugins/

List all registered plugins.

**Response:** Array of `PluginMetadata`:

```json
[
  {
    "name": "labclaw-neuro",
    "version": "0.1.0",
    "description": "Neuroscience domain plugin",
    "author": "Shen Lab",
    "plugin_type": "domain"
  }
]
```

```bash
curl http://localhost:18800/api/plugins/
```

### GET /api/plugins/by-type/{plugin_type}

Filter plugins by type.

**Path parameters:**

| Parameter | Values |
|-----------|--------|
| `plugin_type` | `device`, `domain`, `analysis` |

```bash
curl http://localhost:18800/api/plugins/by-type/domain
```

---

## Orchestrator

Trigger and inspect scientific method loop cycles.

Prefix: `/api/orchestrator`

### POST /api/orchestrator/cycle

Trigger one complete scientific method cycle (OBSERVE through CONCLUDE).

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `data_rows` | array of objects | No | Data rows to process (default: empty) |

**Response:** `CycleResult` (201 Created):

```json
{
  "cycle_id": "abc-123",
  "steps_completed": ["observe", "ask", "hypothesize"],
  "steps_skipped": ["predict", "experiment"],
  "total_duration": 1.23,
  "patterns_found": 3,
  "hypotheses_generated": 2,
  "success": true
}
```

```bash
curl -X POST http://localhost:18800/api/orchestrator/cycle \
  -H "Content-Type: application/json" \
  -d '{"data_rows": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}'
```

### GET /api/orchestrator/history

List all cycle results from the current process lifetime.

**Response:** Array of `CycleResult` objects.

```bash
curl http://localhost:18800/api/orchestrator/history
```

### GET /api/orchestrator/history/{cycle_id}

Get a single cycle result by ID.

**Response:** `CycleResult`.

**Errors:** 404 if not found.

```bash
curl http://localhost:18800/api/orchestrator/history/abc-123
```

---

## Events

Inspect the event registry.

Prefix: `/api/events`

### GET /api/events/

List all registered event types.

**Response:** Array of event name strings.

```bash
curl http://localhost:18800/api/events/
```

Example response:

```json
[
  "hardware.file.detected",
  "discovery.pattern.found",
  "evolution.cycle.started",
  "memory.tier_a.updated",
  "persona.agent.tool_called"
]
```
