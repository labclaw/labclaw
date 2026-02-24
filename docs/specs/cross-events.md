# Cross-Cutting Events Index

**Auto-generated** — aggregated from all layer specs. Do not edit manually.
**Generated from:** 39 registered events across 9 domains.

## Event Naming Convention

```
{layer}.{module}.{action}
```

## L1: Hardware (7 events)

| Event | Module | Action | Source |
|-------|--------|--------|--------|
| `hardware.command.executed` | command | executed | `hardware/manager.py` |
| `hardware.device.registered` | device | registered | `hardware/registry.py` |
| `hardware.device.status_changed` | device | status_changed | `hardware/registry.py` |
| `hardware.device.unregistered` | device | unregistered | `hardware/registry.py` |
| `hardware.file.detected` | file | detected | `edge/watcher.py` |
| `hardware.quality.checked` | quality | checked | `edge/quality.py` |
| `hardware.safety.checked` | safety | checked | `hardware/safety.py` |

## L2: Infrastructure (3 events)

| Event | Module | Action | Source |
|-------|--------|--------|--------|
| `infra.gateway.client_disconnected` | gateway | client_disconnected | `core/gateway.py` |
| `infra.gateway.client_registered` | gateway | client_registered | `core/gateway.py` |
| `infra.gateway.message_routed` | gateway | message_routed | `core/gateway.py` |

## L3: Discovery (3 events)

| Event | Module | Action | Source |
|-------|--------|--------|--------|
| `discovery.hypothesis.created` | hypothesis | created | `discovery/hypothesis.py` |
| `discovery.mining.completed` | mining | completed | `discovery/mining.py` |
| `discovery.pattern.found` | pattern | found | `discovery/mining.py` |

## L3: Optimization (5 events)

| Event | Module | Action | Source |
|-------|--------|--------|--------|
| `optimization.approval.decided` | approval | decided | `optimization/approval.py` |
| `optimization.approval.requested` | approval | requested | `optimization/approval.py` |
| `optimization.proposal.created` | proposal | created | `optimization/optimizer.py` |
| `optimization.result.recorded` | result | recorded | `optimization/optimizer.py` |
| `optimization.safety.checked` | safety | checked | `optimization/safety.py` |

## L3: Validation (3 events)

| Event | Module | Action | Source |
|-------|--------|--------|--------|
| `validation.provenance.built` | provenance | built | `validation/provenance.py` |
| `validation.report.generated` | report | generated | `validation/statistics.py` |
| `validation.test.completed` | test | completed | `validation/statistics.py` |

## L4: Memory (3 events)

| Event | Module | Action | Source |
|-------|--------|--------|--------|
| `memory.search.executed` | search | executed | `memory/markdown.py` |
| `memory.tier_a.created` | tier_a | created | `memory/markdown.py` |
| `memory.tier_a.updated` | tier_a | updated | `memory/markdown.py` |

## L5: Evolution (5 events)

| Event | Module | Action | Source |
|-------|--------|--------|--------|
| `evolution.cycle.advanced` | cycle | advanced | `evolution/engine.py` |
| `evolution.cycle.promoted` | cycle | promoted | `evolution/engine.py` |
| `evolution.cycle.rolled_back` | cycle | rolled_back | `evolution/engine.py` |
| `evolution.cycle.started` | cycle | started | `evolution/engine.py` |
| `evolution.fitness.measured` | fitness | measured | `evolution/fitness.py` |

## L5: Persona (5 events)

| Event | Module | Action | Source |
|-------|--------|--------|--------|
| `persona.benchmark.recorded` | benchmark | recorded | `persona/manager.py` |
| `persona.correction.recorded` | correction | recorded | `persona/manager.py` |
| `persona.member.created` | member | created | `persona/manager.py` |
| `persona.member.demoted` | member | demoted | `persona/manager.py` |
| `persona.member.promoted` | member | promoted | `persona/manager.py` |

## Edge: Sentinel (2 events)

| Event | Module | Action | Source |
|-------|--------|--------|--------|
| `sentinel.alert.raised` | alert | raised | `edge/sentinel.py` |
| `sentinel.check.completed` | check | completed | `edge/sentinel.py` |

## Edge: Session (3 events)

| Event | Module | Action | Source |
|-------|--------|--------|--------|
| `session.chronicle.ended` | chronicle | ended | `edge/session_chronicle.py` |
| `session.chronicle.started` | chronicle | started | `edge/session_chronicle.py` |
| `session.recording.added` | recording | added | `edge/session_chronicle.py` |
