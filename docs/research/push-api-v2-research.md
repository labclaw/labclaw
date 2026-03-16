# Push API v2 Architecture — Research Summary

**Date:** 2026-03-14
**Status:** Research / Design Phase

## 1. Current Architecture (v1): Proxy Model

### Overview

labwork-web is a standalone debug UI that acts as a **proxy** between the user and backend services. It hosts its own LLM conversation loop and forwards tool calls to device-use and labclaw via HTTP.

```
User (browser)
  │
  │ WebSocket (ws://localhost:8430/ws/chat/{session_id})
  ▼
labwork-web (FastAPI, port 8430)
  │
  │ ┌─ OpenRouter API (LLM chat completions, streaming)
  │ │  model: anthropic/claude-sonnet-4.6
  │ │  format: OpenAI function-calling
  │ │
  │ ├─ HTTP GET/POST → device-use (port 8420)
  │ │   /api/datasets, /api/process/{sample}/{expno}, /api/analyze/...
  │ │   /api/pubchem/{compound}, /api/plate-reader/...
  │ │   /api/call_tool/tooluniverse
  │ │
  │ └─ HTTP GET/POST → labclaw (port 18800)
  │     /api/findings, /api/discover
  │
  ▼
Browser renders pipeline + report
```

### How labwork-web Works Today

**Server (`app.py`, ~1180 lines):**

1. **LLM Proxy**: labwork-web maintains its own OpenAI-compatible client (via OpenRouter) with a system prompt defining the "Physical AI Scientist" persona. It defines 11 tools in OpenAI function-calling format (nmr_list_datasets, nmr_process, nmr_analyze, pubchem_lookup, plate_reader_list, plate_reader_process, labclaw_list_findings, labclaw_discover, tooluniverse_find, tooluniverse_call, generate_report).

2. **Session Management**: In-memory session store with message history, token-budget trimming (~60K token window), and multi-round tool-use loops (up to 10 rounds).

3. **Tool Execution**: When the LLM requests a tool call, labwork-web executes it by mapping tool names to REST API endpoints on device-use or labclaw. The `execute_tool()` function proxies HTTP calls.

4. **WebSocket Protocol (13 message types)**: The server pushes real-time updates to the browser over WebSocket:
   - `status` (running/idle)
   - `thinking` (active/done)
   - `delta` (streaming text chunks)
   - `metrics` (tokens, tools_called, round)
   - `tool_start` (tool name, id, description)
   - `tool_end` (parsed args available)
   - `tool_executing` (execution started)
   - `tool_result` (result content)
   - `evidence` (structured data: peaks/compound/analysis)
   - `done` (pipeline complete)
   - `error` / `warning` / `clarification`

5. **VM Frame Push**: There is an existing push mechanism for VM screenshots — `POST /vm/frame` accepts binary JPEG frames, `GET /vm/stream` serves MJPEG to the browser. This is the closest existing precedent for the push model.

6. **Proxy Endpoints**: `GET /api/device-use/{path}` and `GET /api/labclaw/{path}` forward requests to the respective backends.

**Frontend (dual implementations):**

- **Legacy (`static-legacy/app.js`)**: Vanilla JS, ~1018 lines. Connects via WebSocket, renders a scientific pipeline (OBSERVE/ANALYZE/HYPOTHESIZE/VERIFY/REPORT/RECOMMEND steps), instrument panel (NMR spectrum SVG + peak assignments), and report panel.
- **React (`frontend/src/`)**: React 18 + TypeScript + Tailwind + Framer Motion. Uses hooks: `useWebSocket`, `usePipelineReducer`, `useServiceHealth`, `useVMStatus`. Typed WebSocket messages in `types.ts`.

### How device-use MCP Works

Defined in `.mcp.json`, started as a stdio subprocess by Claude Code:
```json
{
  "command": ".venv/bin/python",
  "args": ["-m", "device_use.integrations.mcp_server"],
  "env": { "PYTHONPATH": "src" }
}
```

The MCP server (`device_use/integrations/mcp_server.py`) exposes 9 tools via FastMCP:
- `list_instruments()` — enumerate registered instruments
- `list_tools()` — enumerate available instrument tools
- `call_tool(tool_name, params)` — call any registered tool by name
- `nmr_list_datasets()` — list NMR datasets
- `nmr_process(data_path)` — FFT + phase + baseline + peaks
- `nmr_identify(data_path, molecular_formula)` — process + AI identification
- `plate_reader_list_assays()` — list plate reader datasets
- `plate_reader_process(assay_name)` — run plate reader assay
- `run_pipeline(steps_json)` — multi-step pipeline execution

Plus 1 resource: `device-use://status`

### How labclaw MCP Works

Also defined in `.mcp.json`, started as a stdio subprocess:
```json
{
  "command": ".venv/bin/python",
  "args": ["-m", "labclaw.mcp.server"]
}
```

The MCP server (`labclaw/mcp/server.py`) exposes 7 tools via FastMCP:
- `discover(min_sessions, correlation_threshold, anomaly_z_threshold)` — pattern mining
- `hypothesize(context, constraints)` — generate hypotheses
- `evolution_status()` — self-evolution cycle status
- `device_status()` — list lab devices
- `query_memory(query)` — search lab memory with provenance
- `list_findings(limit)` — list recent findings
- `provenance(finding_id)` — full traceability chain

---

## 2. Proposed v2 Architecture: Push Model

### Core Idea

In v1, labwork-web owns the LLM loop — it calls OpenRouter, executes tools, and pushes results to the browser. This means the "brain" is an OpenRouter-proxied Sonnet.

In v2, **Claude Code (Opus 4.6) IS the brain**. It calls MCP tools directly (device-use, labclaw). The question is: how does the frontend see what Claude Code is doing?

```
v1 (current):
  Browser ──WS──▶ labwork-web ──HTTP──▶ device-use/labclaw
                      │
                      └── OpenRouter (LLM)

v2 (proposed):
  Claude Code (Opus 4.6, main thread)
      │
      ├── MCP stdio ──▶ device-use (instruments)
      ├── MCP stdio ──▶ labclaw (memory, discovery)
      │
      └── Push API ──▶ labwork-web ──WS──▶ Browser
```

### Communication Path

Claude Code calls MCP tools as it normally does. After each tool call or reasoning step, it also pushes a status event to labwork-web, which relays it to connected browsers via WebSocket.

```
Claude Code
  │
  │ 1. Calls MCP tool (e.g., nmr_process)
  │ 2. Gets result from device-use
  │ 3. POST /push/event to labwork-web
  │
  ▼
labwork-web (port 8430)
  │
  │ Relays event over existing WebSocket
  │
  ▼
Browser (renders pipeline, instrument data, report)
```

### New Endpoints Needed on labwork-web

labwork-web becomes a **display server** rather than a proxy. It needs:

#### Push Ingest Endpoints

1. **`POST /push/event`** — Generic event push (replaces the internal WebSocket emit logic)
   ```json
   {
     "type": "tool_start" | "tool_result" | "delta" | "status" | ...,
     "session_id": "optional — broadcast if omitted",
     ...existing fields from WSMessage types...
   }
   ```

2. **`POST /push/batch`** — Batch multiple events (reduces HTTP overhead)
   ```json
   {
     "events": [
       { "type": "status", "status": "running" },
       { "type": "tool_start", "name": "nmr_process", "id": "...", "description": "..." }
     ]
   }
   ```

3. **`POST /push/frame`** — Already exists as `POST /vm/frame`. Generalize for any visual output (spectrum images, heatmaps, screenshots).

#### Display Endpoints (already exist, keep as-is)

- `GET /ws/chat/{session_id}` — Browser WebSocket (read-only in v2, no prompt sending)
- `GET /api/config` — Frontend config
- `GET /vm/stream` — MJPEG stream (already push-based)

#### Removed/Deprecated

- OpenRouter LLM client code — no longer needed, Claude Code is the brain
- `execute_tool()` function — no longer proxies tool calls
- Tool definitions (TOOLS list) — tools are defined in MCP servers
- Session management / message history — Claude Code manages its own context

### WebSocket Protocol Changes

The existing 13 message types are a good fit. Minor changes:

| Message Type | v1 Source | v2 Source |
|---|---|---|
| `status` | labwork-web internal | Claude Code pushes `POST /push/event` |
| `thinking` | labwork-web detects first text delta | Claude Code pushes when reasoning |
| `delta` | OpenRouter streaming chunks | Claude Code pushes text chunks |
| `tool_start` | labwork-web parses streaming tool_calls | Claude Code pushes before MCP call |
| `tool_end` | labwork-web finishes parsing args | Claude Code pushes after args parsed |
| `tool_executing` | labwork-web about to call execute_tool | Claude Code pushes before MCP execution |
| `tool_result` | labwork-web gets HTTP response | Claude Code pushes MCP result |
| `evidence` | labwork-web parses tool result | Claude Code pushes structured evidence |
| `metrics` | labwork-web counts tokens/rounds | Claude Code pushes its own metrics |
| `done` | labwork-web loop exits | Claude Code pushes when task complete |
| `error`/`warning` | labwork-web catches exceptions | Claude Code pushes errors |
| `clarification` | labwork-web detects question | Claude Code pushes when asking user |

### Implementation Options

#### Option A: HTTP Push (Simplest)

Claude Code uses `curl` or an MCP tool to POST events to labwork-web.

**Pros:**
- No new infrastructure — labwork-web already handles HTTP
- Claude Code can push from any tool (Bash, custom MCP)
- Works with existing WebSocket relay

**Cons:**
- HTTP overhead per event (mitigated by batch endpoint)
- Requires labwork-web running and reachable
- One-way: browser cannot send prompts back through this path

**Implementation:**
- Add `POST /push/event` endpoint to labwork-web
- Create a thin MCP tool or wrapper that Claude Code calls after each action
- labwork-web broadcasts to all connected WebSocket clients

#### Option B: Shared Event Bus (Redis/file)

Claude Code writes events to a shared store (Redis Stream, SQLite, or a file). labwork-web polls or subscribes to the store and relays to browsers.

**Pros:**
- Decoupled — labwork-web doesn't need to be running when events are produced
- Events are persisted, can be replayed
- Multiple consumers possible

**Cons:**
- Requires shared state infrastructure
- Polling adds latency (Redis Streams would be real-time)
- More complex setup

#### Option C: labwork-web MCP Server

labwork-web itself becomes an MCP server that Claude Code connects to. Claude Code calls `push_event(...)` as an MCP tool.

**Pros:**
- Native MCP integration — Claude Code sees it as just another tool
- Bidirectional potential (labwork-web could also expose tools)
- Type-safe tool definitions

**Cons:**
- MCP stdio transport requires process management
- labwork-web would need both HTTP server (for browser) and MCP server (for Claude Code)
- More complex than HTTP push

### Recommended Approach: Option A (HTTP Push) + MCP Wrapper

1. Add `POST /push/event` and `POST /push/batch` to labwork-web
2. Create a small MCP tool (or extend device-use MCP) with a `push_ui_event(type, data)` tool
3. Claude Code calls `push_ui_event` after significant actions
4. labwork-web relays to browser over existing WebSocket

This approach reuses the existing WebSocket protocol (all 13 message types), requires minimal changes to the frontend, and adds only ~50 lines to labwork-web.

---

## 3. Key Changes Needed

### labwork-web Changes

| Component | v1 | v2 |
|---|---|---|
| `app.py` main server | ~1180 lines (LLM + proxy + tools) | ~300 lines (push relay + static files) |
| LLM client code | OpenRouter AsyncOpenAI | REMOVED |
| Tool definitions (TOOLS) | 11 OpenAI function-calling defs | REMOVED |
| `execute_tool()` | HTTP proxy to device-use/labclaw | REMOVED |
| Session/history management | In-memory, token trimming | REMOVED (Claude Code manages) |
| System prompt | SYSTEM_PROMPT constant | REMOVED |
| WebSocket handler | Receives user prompt, runs LLM loop, pushes events | Receives user prompt (optional), relays to Claude Code or just receives push events |
| `POST /push/event` | Does not exist | NEW — accepts events, broadcasts to WS clients |
| `POST /push/batch` | Does not exist | NEW — batch event push |
| Proxy endpoints | `/api/device-use/...`, `/api/labclaw/...` | KEEP for health checks; remove tool proxying |
| VM frame push | `POST /vm/frame` (exists) | KEEP, generalize |
| Frontend JS/React | Renders pipeline from WS events | KEEP — same protocol, different event source |

### MCP Server Changes

| Component | Change |
|---|---|
| device-use MCP | No change — Claude Code calls it directly |
| labclaw MCP | No change — Claude Code calls it directly |
| NEW: UI push MCP | Add `push_ui_event(type, payload)` tool that POSTs to labwork-web |

### Frontend Changes

| Component | Change |
|---|---|
| WebSocket protocol | NO CHANGE — same 13 message types |
| Pipeline rendering | NO CHANGE |
| Instrument panel | NO CHANGE |
| Report panel | NO CHANGE |
| Prompt input | CHANGE — either remove (Claude Code drives) or add bidirectional channel |
| Service health | KEEP — still poll device-use and labclaw status |

---

## 4. Open Questions

### Q1: User Input Flow

In v1, the user types a prompt in the browser, which sends it over WebSocket to labwork-web, which sends it to the LLM. In v2, Claude Code is the brain. How does the user interact?

**Options:**
- **a) Browser prompt -> labwork-web -> Claude Code**: Requires a mechanism for labwork-web to send messages to Claude Code. This is hard because Claude Code is a CLI process, not an HTTP server. Could use a file-based or Redis-based message queue.
- **b) User types in Claude Code terminal directly**: labwork-web becomes display-only, no prompt input. Simple but changes the UX.
- **c) Hybrid**: User can type in either place. Browser prompts go to a simple chat endpoint that uses a lighter model. Claude Code handles complex tasks.

### Q2: Session Lifecycle

Who starts and ends sessions? In v1, labwork-web creates sessions on demand. In v2, Claude Code drives the workflow. Does Claude Code create a session via POST, or does labwork-web auto-create on first push event?

### Q3: Multiple Browsers

Should multiple browser tabs see the same push events? The VM frame endpoint already broadcasts. The push endpoint should probably broadcast to all connected WebSocket clients for a given session (or globally if no session).

### Q4: Bidirectional MCP

MCP is inherently bidirectional (client can call server tools, server can send notifications). Could labwork-web be an MCP server that Claude Code connects to, using MCP notifications for push events? This would be more "MCP-native" but adds complexity.

### Q5: What About labwork (Electron)?

The Electron desktop app (`labwork/`) also connects to device-use and labclaw via MCP. Does it need the push API too, or is this labwork-web only? If labwork also needs it, the push MCP tool should be a separate, reusable component.

### Q6: Offline / Replay

Should push events be persisted so a browser can connect late and replay the session? This would require a simple event log (append-only file or SQLite table). The VM log endpoint (`/vm/log`) is a precedent.

### Q7: Authentication

v1 restricts to localhost only (`_is_loopback_host` middleware). v2 push endpoint should also be localhost-only (Claude Code runs locally). But if labwork-web is ever exposed on a network, the push endpoint needs auth (API key or token).

---

## 5. Rough Implementation Plan

### Phase 1: Push Relay (~50 LOC in labwork-web)
- Add `POST /push/event` endpoint
- Maintain a set of connected WebSocket clients
- Broadcast incoming events to all clients
- Add `POST /push/batch` for efficiency

### Phase 2: UI Push MCP Tool (~30 LOC)
- Add `push_ui_event(type, payload)` to device-use MCP server (or create a new `labwork-web` MCP server)
- Claude Code calls this after MCP tool results, reasoning steps, etc.

### Phase 3: Slim Down labwork-web (~delete 800 LOC)
- Remove LLM client, tool definitions, execute_tool, session management
- Keep: push endpoints, WebSocket relay, proxy endpoints (health), VM frame, static files

### Phase 4: Frontend Adjustments (~minimal)
- WebSocket protocol unchanged
- Optionally remove or simplify prompt input
- Add connection status indicator for push source

### Phase 5: Workflow Integration
- Define Claude Code workflow: when to push events (before/after MCP calls, during reasoning)
- Test end-to-end: Claude Code -> MCP tools -> push events -> browser display

---

## 6. Appendix: File Inventory

| File | Role | Lines |
|---|---|---|
| `/Users/robert/workspace/36-labclaw/labwork-web/app.py` | Main server (LLM + proxy + WS) | ~1180 |
| `/Users/robert/workspace/36-labclaw/labwork-web/static-legacy/app.js` | Legacy vanilla JS frontend | ~1018 |
| `/Users/robert/workspace/36-labclaw/labwork-web/static-legacy/index.html` | Legacy HTML (3-panel layout) | ~192 |
| `/Users/robert/workspace/36-labclaw/labwork-web/frontend/src/App.tsx` | React frontend | ~700+ |
| `/Users/robert/workspace/36-labclaw/labwork-web/frontend/src/types.ts` | WebSocket message types (13 types) | ~240 |
| `/Users/robert/workspace/36-labclaw/labwork-web/frontend/src/hooks/useWebSocket.ts` | React WebSocket hook | ~139 |
| `/Users/robert/workspace/36-labclaw/labwork-web/frontend/src/hooks/usePipelineReducer.ts` | Pipeline state reducer | ? |
| `/Users/robert/workspace/36-labclaw/.mcp.json` | MCP server config (device-use + labclaw + drawio) | ~21 |
| `/Users/robert/workspace/36-labclaw/device-use/src/device_use/integrations/mcp_server.py` | device-use MCP (9 tools, 1 resource) | ~285 |
| `/Users/robert/workspace/36-labclaw/labclaw/src/labclaw/mcp/server.py` | labclaw MCP (7 tools) | ~300 |
