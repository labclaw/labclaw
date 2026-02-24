# Self-Evolution

LabClaw improves its own analytical strategies without human intervention. The
evolution engine continuously measures performance, proposes configuration changes,
tests them through a staged promotion pipeline, and automatically rolls back if
performance degrades.

---

## Concept

Traditional data analysis pipelines use fixed parameters. LabClaw treats these
parameters as evolvable: thresholds, routing rules, LLM prompts, and high-level
strategy are all candidates for automatic improvement.

The system measures its own fitness (how well it discovers patterns, how accurate
its predictions are), proposes variations, and promotes the best performers through
a safe staged pipeline.

---

## Evolution Targets

Five categories of configuration can evolve independently:

| Target | What changes | Example parameters |
|--------|-------------|-------------------|
| `analysis_params` | Mining thresholds, clustering settings | `correlation_threshold: 0.5`, `anomaly_z_threshold: 2.0` |
| `prompts` | LLM system prompts for hypothesis generation | `temperature: 0.7`, `max_tokens: 2048` |
| `routing` | Which analysis module handles which data type | `priority_weight: 0.5`, `timeout_seconds: 30` |
| `heuristics` | Decision rules for anomaly flagging | `confidence_floor: 0.5`, `max_retries: 3` |
| `strategy` | High-level experiment selection logic | `pipeline_order: "correlations_first"`, `parallel: true` |

Each target evolves independently with its own fitness history.

---

## Fitness Functions

Fitness is measured as a set of named metrics for each target. The evolution engine
tracks these over time and compares candidates against baselines.

```python
from labclaw.evolution.engine import EvolutionEngine
from labclaw.core.schemas import EvolutionTarget

engine = EvolutionEngine()

# Record current fitness
fitness = engine.measure_fitness(
    target=EvolutionTarget.ANALYSIS_PARAMS,
    metrics={
        "pattern_count": 12.0,
        "coverage": 0.8,
        "data_rows": 500.0,
    },
    data_points=500,
)
```

Fitness scores include:

- `target`: Which evolution target this measures.
- `metrics`: Dict of metric names to float values. Higher is better.
- `measured_at`: Timestamp of measurement.
- `data_points`: Number of observations used.

The FitnessTracker keeps full history per target, enabling trend analysis.

---

## The 7-Step Cycle

Evolution follows a structured pipeline, implemented in `EvolutionEngine`:

### 1. MEASURE

Compute fitness metrics for the current production configuration by running the
analysis pipeline on accumulated data.

### 2. PROPOSE

Generate candidate configuration variants. Two proposal strategies:

- **Template-based** (default): Pick from predefined parameter variations.
- **LLM-powered**: Use the LLM to analyze fitness history and propose smarter changes.

```python
# Template-based
candidates = engine.propose_candidates(EvolutionTarget.ANALYSIS_PARAMS, n=3)

# LLM-powered (async)
candidates = await engine.propose_candidates_llm(
    target=EvolutionTarget.ANALYSIS_PARAMS,
    context="Pattern count has plateaued at 12 for 5 cycles",
    llm_provider=provider,
    n=3,
)
```

Each candidate contains a `config_diff` -- the specific parameter changes to test.

### 3. BACKTEST

Replay historical data through the candidate configuration. Compare its fitness
metrics against the baseline.

```python
cycle = engine.start_cycle(candidate=candidates[0], baseline=fitness)
# cycle.stage == EvolutionStage.BACKTEST
```

### 4. SHADOW

Run both production and candidate configurations in parallel on live data.
The candidate's output is recorded but does not affect production results.

```python
# After backtest passes, advance to shadow
cycle = engine.advance_stage(cycle.cycle_id, new_fitness=shadow_fitness)
# cycle.stage == EvolutionStage.SHADOW
```

### 5. CANARY

Route a fraction of live traffic to the candidate. Monitor for regressions.

```python
cycle = engine.advance_stage(cycle.cycle_id, new_fitness=canary_fitness)
# cycle.stage == EvolutionStage.CANARY
```

### 6. PROMOTE

If the candidate passes all stages without regression, it becomes the new
production configuration.

```python
cycle = engine.advance_stage(cycle.cycle_id, new_fitness=final_fitness)
# cycle.stage == EvolutionStage.PROMOTED
# cycle.promoted == True
```

### 7. ROLLBACK

If fitness drops at any stage, the system automatically reverts to the
previous configuration.

```python
# Automatic: happens inside advance_stage if regression detected
# Manual:
cycle = engine.rollback(cycle.cycle_id, reason="PI requested rollback")
```

---

## Stage Transition Diagram

```
BACKTEST ──> SHADOW ──> CANARY ──> PROMOTED
    │           │          │
    └───────────┴──────────┴───> ROLLED_BACK
                                 (if fitness drops > threshold)
```

Each transition requires passing the regression check: no metric may drop more
than `rollback_threshold` (default 10%) from baseline.

---

## Auto-Rollback

The regression check runs at every stage transition:

```python
drop = (baseline_value - current_value) / abs(baseline_value)
if drop > rollback_threshold:
    # Auto-rollback triggered
```

For each metric in the baseline fitness, the engine computes the relative drop.
If any single metric exceeds the threshold, the entire cycle is rolled back.

Events emitted:

- `evolution.cycle.rolled_back` -- includes cycle_id, reason, and stage at rollback.

---

## Tuning Parameters

Configured via `EvolutionConfig`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_soak_sessions` | 5 | Minimum time (seconds) before a cycle can advance to next stage |
| `rollback_threshold` | 0.1 | Maximum allowed relative fitness drop (10%) before auto-rollback |
| `max_candidates` | 3 | Maximum candidates to propose at once |
| `diversity_min` | 2 | Minimum distinct parameter changes across candidates |
| `max_cycles` | 1000 | Maximum stored cycles (oldest evicted when exceeded) |

```python
from labclaw.evolution.schemas import EvolutionConfig

config = EvolutionConfig(
    min_soak_sessions=10,
    rollback_threshold=0.05,  # Stricter: 5% threshold
    max_cycles=500,
)
engine = EvolutionEngine(config=config)
```

---

## LLM-Powered Proposals

When an LLM provider is available, the engine can generate smarter candidates
by analyzing fitness history:

```python
candidates = await engine.propose_candidates_llm(
    target=EvolutionTarget.ANALYSIS_PARAMS,
    context="Lab processes fluorescence imaging data. Recent patterns show diminishing returns.",
    llm_provider=provider,
    n=3,
)
```

The LLM receives:

- The evolution target.
- Domain context from the caller.
- Recent fitness history (last 5 measurements).

It returns a JSON array of `{"description": ..., "config_diff": ...}` proposals.

If the LLM call fails, the engine falls back to template-based proposals.

---

## State Persistence

Evolution state survives restarts via JSON persistence:

```python
# Save state
engine.persist_state(Path("memory/evolution_state.json"))

# Load state on startup
engine.load_state(Path("memory/evolution_state.json"))
```

The daemon automatically persists state after each evolution interval and loads
it on startup.

Persisted state includes:

- All cycles (active, promoted, and rolled-back).
- Complete fitness history per target.
- Timestamp of last save.

---

## Daemon Integration

The LabClaw daemon runs evolution automatically:

1. Every 30 minutes (configurable via `--evolution-interval`), the daemon:
   - Computes current fitness from accumulated data.
   - Advances any active cycles that have soaked long enough.
   - Starts new cycles if none are active.
   - Persists state to disk.

2. Evolution events are logged to Tier A memory.

3. The Streamlit dashboard shows evolution progress in real time.

---

## API Access

Query and trigger evolution via the REST API:

```bash
# View cycle history
curl http://localhost:18800/api/evolution/history

# Measure fitness
curl -X POST http://localhost:18800/api/evolution/fitness \
  -H "Content-Type: application/json" \
  -d '{"target": "analysis_params", "metrics": {"pattern_count": 15.0}}'

# Start a new cycle
curl -X POST http://localhost:18800/api/evolution/cycle \
  -H "Content-Type: application/json" \
  -d '{"target": "analysis_params"}'
```

See [API Reference](api-reference.md) for full endpoint documentation.
