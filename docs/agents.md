# Agent System

LabClaw includes an agent runtime that enables LLM-backed assistants to interact
with the lab system through registered tools. Agents use a ReAct-style loop:
reason about the question, call tools to gather data, and synthesize a response.

---

## Built-in Agents

### Lab Assistant

General-purpose assistant for day-to-day lab questions.

**Capabilities:**
- Answer questions about lab data, patterns, and findings.
- Explain discovered correlations and anomalies.
- Summarize recent discoveries and evolution progress.
- Suggest what to investigate next.

**API endpoint:** `POST /api/agents/chat`

```bash
curl -X POST http://localhost:18800/api/agents/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What patterns did you find today?"}'
```

### Experiment Designer

Specialized agent for planning experiments.

**Capabilities:**
- Suggest the most informative next experiment.
- Estimate statistical power and sample sizes.
- Consider practical constraints (time, equipment, reagents).
- Prioritize experiments that test key hypotheses.

**API endpoint:** `POST /api/agents/designer/chat`

```bash
curl -X POST http://localhost:18800/api/agents/designer/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Given the speed-accuracy tradeoff, what should we test next?"}'
```

---

## Built-in Tools

Agents have access to 7 built-in tools that interact with LabClaw's subsystems.

### query_memory

Search Tier A memory for past findings, patterns, and conclusions.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search query text |

### run_mining

Run pattern mining on provided data rows.

| Parameter | Type | Description |
|-----------|------|-------------|
| `data_rows` | array of dicts | Tabular data to mine |

### hypothesize

Generate testable hypotheses from discovered patterns.

| Parameter | Type | Description |
|-----------|------|-------------|
| `patterns` | array of dicts | Patterns to generate hypotheses from |

### device_status

List all lab devices and their current status. No parameters.

### propose_experiment

Suggest next experiment parameters for a given hypothesis.

| Parameter | Type | Description |
|-----------|------|-------------|
| `hypothesis_id` | string | ID of the hypothesis to design an experiment for |

### get_evolution_status

Get current self-evolution cycle status. No parameters.

### search_findings

Search findings and conclusions from scientific cycles.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search query text |

### List All Tools via API

```bash
curl http://localhost:18800/api/agents/tools
```

---

## ReAct Loop Architecture

The `AgentRuntime` implements a ReAct-style (Reason + Act) loop:

```
User message
     |
     v
Build prompt (tools + history)
     |
     v
Send to LLM
     |
     v
Parse response ─── Plain text? ──> Return to user
     |
     No (contains tool call)
     |
     v
Execute tool
     |
     v
Feed result back to LLM
     |
     v
Loop (up to max_turns)
```

### Flow Details

1. **User sends a message** via the API.
2. **Runtime builds a prompt** that includes:
   - Tool descriptions with parameter schemas.
   - Full conversation history.
3. **LLM generates a response.** If it wants to call a tool, it outputs JSON:
   ```json
   {"tool": "query_memory", "arguments": {"query": "calcium imaging results"}}
   ```
4. **Runtime executes the tool** and gets a `ToolResult`.
5. **Tool result is fed back** to the LLM as context.
6. Steps 3-5 repeat until:
   - The LLM responds with plain text (no tool call), or
   - Maximum turns (10) are reached.

### Message History

The runtime maintains a conversation history:

```python
runtime = AgentRuntime(llm_provider=provider)
# Each call to chat() appends user/assistant/tool messages
response = await runtime.chat("What patterns exist?")
# runtime.message_history contains the full conversation

# Clear history to start fresh
runtime.clear_history()
```

---

## Creating Custom Agents

### Custom Tool

Create a tool by wrapping an async function in `AgentTool`:

```python
from labclaw.agents.tools import AgentTool, ToolResult

async def check_temperature(device_id: str) -> ToolResult:
    """Read temperature from a specific device."""
    # Your implementation here
    return ToolResult(success=True, data={"temperature": 37.2, "unit": "C"})

temperature_tool = AgentTool(
    name="check_temperature",
    description="Read temperature from a lab device.",
    fn=check_temperature,
    parameters_schema={
        "device_id": {"type": "string", "description": "Device ID to query"},
    },
)
```

### Custom Agent

```python
from labclaw.agents.runtime import AgentRuntime
from labclaw.agents.tools import build_builtin_tools

# Start with built-in tools
tools = build_builtin_tools(
    memory_root=memory_root,
    device_registry=device_registry,
)

# Add custom tools
tools.append(temperature_tool)

# Create runtime
runtime = AgentRuntime(llm_provider=provider, tools=tools)

# Chat with custom system prompt
response = await runtime.chat(
    "What is the temperature in the imaging room?",
    system_prompt="You are a lab safety monitor...",
)
```

### Factory Functions

For convenience, use the built-in factories:

```python
from labclaw.agents import create_lab_assistant, create_experiment_designer

# Lab Assistant with all built-in tools
assistant = create_lab_assistant(
    llm=provider,
    memory_root=memory_root,
    device_registry=device_registry,
    evolution_engine=evolution_engine,
)

# Experiment Designer with all built-in tools
designer = create_experiment_designer(
    llm=provider,
    memory_root=memory_root,
    device_registry=device_registry,
)
```

---

## MCP Server for External AI Integration

LabClaw exposes its capabilities as an MCP (Model Context Protocol) server,
allowing external AI tools (Claude Desktop, etc.) to use lab intelligence.

### Start the MCP Server

```bash
labclaw mcp
```

This starts an MCP server on stdio transport.

### Configure Claude Desktop

Add to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "labclaw": {
      "command": "labclaw",
      "args": ["mcp"]
    }
  }
}
```

### Available MCP Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `discover` | `min_sessions`, `correlation_threshold`, `anomaly_z_threshold` | Run pattern mining |
| `hypothesize` | `context`, `constraints` | Generate hypotheses |
| `evolution_status` | (none) | Get evolution cycle status |
| `device_status` | (none) | List devices and status |
| `query_memory` | `query` | Search lab memory |
| `list_findings` | `limit` | List recent findings |

### Usage from Claude

Once configured, Claude can naturally use lab tools:

> "What patterns has the lab found recently?"

Claude calls `query_memory` and `list_findings` to answer.

> "Run discovery on the latest behavioral data"

Claude calls `discover` with appropriate parameters.

---

## Events

The agent system emits events for monitoring:

| Event | When |
|-------|------|
| `persona.agent.message_received` | User sends a message |
| `persona.agent.tool_called` | Agent invokes a tool |
| `persona.agent.response_generated` | Agent produces final response |
