# LabClaw

**Cloud Brain — unified gateway to 2400+ scientific tools.**

LabClaw gives scientists and developers a single interface to access scientific databases and AI tools: PubMed, UniProt, ChEMBL, PubChem, OpenTargets, and 2000+ more via [ToolUniverse](https://github.com/mims-harvard/ToolUniverse).

## Install

```bash
pip install labclaw
# For ToolUniverse tools:
pip install labclaw[tooluniverse]
# For LLM-powered features (reasoning, writing):
pip install labclaw[llm]
# Everything:
pip install labclaw[all]
```

## Quick Start

```bash
# Try it
labclaw demo

# Start Cloud Brain REST API
labclaw brain

# Start MCP server (for Claude Desktop)
labclaw mcp

# List available tools
labclaw tools
```

## Python SDK

```python
from labclaw.brain import execute, list_tools, reason, write

# Search PubMed
result = await execute("search_pubmed", query="CRISPR delivery")

# Life science reasoning
answer = await reason("What controls circadian rhythm in Drosophila?")

# Scientific writing
section = await write(section="methods", context="We performed RNA-seq on 3 replicates...")

# List tools
tools = await list_tools(category="genomics")
```

## REST API

```bash
curl http://localhost:18802/brain/health
curl http://localhost:18802/brain/tools
curl -X POST http://localhost:18802/brain/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "search_pubmed", "arguments": {"query": "CRISPR"}}'
```

## Claude Desktop (MCP)

Add to your Claude Desktop config:
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

## Part of the LabClaw Ecosystem

| Repo | What it does |
|------|-------------|
| **labclaw** (this) | Cloud Brain — scientific tool gateway |
| [lab-manager](https://github.com/labclaw/lab-manager) | AI lab data management |
| [device-use](https://github.com/labclaw/device-use) | AI instrument control |
| [dollar-lab](https://github.com/labclaw/dollar-lab) | $0.002 microscope optimization demo |

## License

Apache 2.0
