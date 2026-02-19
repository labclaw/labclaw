---
name: review-checklist
description: "Generate a domain-specific code review checklist for recent changes, covering architecture compliance, neuroscience data standards, and safety requirements."
user-invocable: true
allowed-tools: Bash, Read, Grep, Glob
context: fork
---

You are generating a code review checklist for Jarvis Mesh.

## Context

1. Get recent changes:
```bash
git diff --stat HEAD~1 2>/dev/null || git diff --stat --cached 2>/dev/null || echo "No recent changes"
```

2. Get changed files:
```bash
git diff --name-only HEAD~1 2>/dev/null || git diff --name-only --cached 2>/dev/null || echo "None"
```

## Generate Checklist

Based on the changed files, generate a checklist covering:

### Architecture
- [ ] Plugin pattern followed (manifest + registry, not hardcoded)?
- [ ] Experiment graph used as source of truth?
- [ ] Edge nodes remain autonomous (offline-capable)?

### Data Standards
- [ ] NWB-compatible schemas (if touching graph/schema code)?
- [ ] Subject metadata complete (species, genotype, age, sex)?
- [ ] File references use paths + checksums (not embedded data)?

### Safety
- [ ] No credentials in code?
- [ ] Device actions gated by approval?
- [ ] Audit logging for agent actions?
- [ ] No force push or destructive git operations?

### Code Quality
- [ ] Type hints on public functions?
- [ ] Pydantic models for data validation?
- [ ] Tests for new functionality?
- [ ] ruff lint passes?
- [ ] numpy types cast before JSON serialization?

### Domain-Specific (if applicable)
- [ ] Quality metrics scientifically meaningful?
- [ ] Analysis pipeline DAG correct (inputs → outputs)?
- [ ] Closed-loop optimization within safe parameter bounds?

Print the checklist with items marked as relevant or N/A based on which files changed.
