# L5 Self-Evolution Spec

**Design doc reference:** section 8.3 (7-step evolution cycle)

## Purpose

The self-evolution subsystem enables Jarvis Mesh to improve its own analytical
strategies autonomously.  Rather than tuning only experiment parameters
(Bayesian optimization in L3), this layer mutates the system's internal
configuration — analysis parameters, prompts, routing rules, heuristics, and
high-level strategy — through a rigorous promotion pipeline with regression
prevention.

## Evolution Targets

Five mutable dimensions (see `EvolutionTarget` enum in `core/schemas.py`):

| Target | Example | Fitness Metrics |
|--------|---------|-----------------|
| `analysis_params` | correlation threshold, z-score cutoff | accuracy, efficiency |
| `prompts` | hypothesis generation prompt | hit_rate, coherence |
| `routing` | agent task routing weights | latency, success_rate |
| `heuristics` | anomaly detection rules | precision, recall |
| `strategy` | mining pipeline ordering | throughput, discovery_rate |

## 7-Step Cycle

1. **MEASURE** — record current strategy fitness via `FitnessTracker`.
2. **PROPOSE** — generate N candidate config variants (template-based MVP,
   LLM-based in future).
3. **BACKTEST** — replay candidate against historical data offline.
4. **SHADOW** — run candidate alongside production, compare outputs.
5. **CANARY** — apply candidate to low-risk subset only.
6. **PROMOTE** — candidate becomes the new stable config.
7. **MONITOR** — continuous fitness tracking; auto-rollback if regression.

Stage transitions: `BACKTEST → SHADOW → CANARY → PROMOTED`.
At each advance, fitness is compared to baseline.  If any metric drops by more
than `rollback_threshold` (default 10 %), the cycle is auto-rolled back.

## Pydantic Schemas

All models live in `src/jarvis_mesh/evolution/schemas.py`.

### FitnessScore

```python
class FitnessScore(BaseModel):
    target: EvolutionTarget
    metrics: dict[str, float]
    measured_at: datetime
    data_points: int
```

### EvolutionCandidate

```python
class EvolutionCandidate(BaseModel):
    candidate_id: str            # uuid4
    target: EvolutionTarget
    description: str
    config_diff: dict[str, Any]
    proposed_at: datetime
    proposed_by: str             # "system" or member id
```

### EvolutionCycle

```python
class EvolutionCycle(BaseModel):
    cycle_id: str
    target: EvolutionTarget
    candidate: EvolutionCandidate
    baseline_fitness: FitnessScore
    current_fitness: FitnessScore | None
    stage: EvolutionStage
    started_at: datetime
    completed_at: datetime | None
    promoted: bool
    rollback_reason: str | None
```

### EvolutionConfig

```python
class EvolutionConfig(BaseModel):
    min_soak_sessions: int  = 5
    rollback_threshold: float = 0.1   # 10 %
    max_candidates: int = 3
    diversity_min: int = 2
```

## Public Interface — EvolutionEngine

```python
class EvolutionEngine:
    def measure_fitness(target, metrics, data_points) -> FitnessScore
    def propose_candidates(target, n) -> list[EvolutionCandidate]
    def start_cycle(candidate, baseline) -> EvolutionCycle
    def advance_stage(cycle_id, new_fitness) -> EvolutionCycle
    def rollback(cycle_id, reason) -> EvolutionCycle
    def get_history(target) -> list[EvolutionCycle]
```

## Events

| Event Name | Payload | Emitted When |
|------------|---------|-------------|
| `evolution.cycle.started` | cycle_id, target, candidate_id | `start_cycle()` |
| `evolution.cycle.advanced` | cycle_id, from_stage, to_stage | `advance_stage()` success |
| `evolution.cycle.promoted` | cycle_id, target, fitness | stage reaches PROMOTED |
| `evolution.cycle.rolled_back` | cycle_id, reason, stage | rollback triggered |
| `evolution.fitness.measured` | target, metrics, data_points | `measure_fitness()` |

## Rollback Rules

- Auto-rollback during `advance_stage()` if any metric value in `new_fitness`
  is more than `rollback_threshold` below the corresponding baseline metric.
- Manual rollback via `rollback(cycle_id, reason)`.
- Rolled-back cycles set `stage = ROLLED_BACK`, `promoted = False`,
  `rollback_reason` populated, `completed_at` set.
