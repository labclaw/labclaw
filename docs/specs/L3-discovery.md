# L3 Discovery Spec

**Layer:** Discovery (L3 — Engine)
**Design doc reference:** Section 5.3 (Discovery Loop)

## Purpose

The discovery layer implements the ASK and HYPOTHESIZE steps of the scientific method
loop. Instead of humans asking questions limited by what they happened to observe,
the system exhaustively mines all variable pairs and time scales for statistically
significant patterns, then generates testable hypotheses from those patterns.

Key capabilities:
- Cross-session correlation discovery (all numeric variable pairs)
- Anomaly detection via z-score analysis
- Temporal pattern detection (trends, rolling mean shifts)
- Template-based hypothesis generation (MVP; LLM-driven in future)
- All findings written to Knowledge Graph with provenance
- Output: ranked list of hypotheses with confidence, testability, and resource estimates

This layer depends on Phase 0 foundations (core schemas, events, graph nodes) and
reads from Memory (Tier A). It feeds into Optimization (L3) and Validation (L3).

---

## Pydantic Schemas

### MiningConfig

```python
class MiningConfig(BaseModel):
    """Configuration for the pattern mining pipeline."""
    min_sessions: int = 10              # Minimum rows required to mine
    correlation_threshold: float = 0.5  # |r| above this is reported
    anomaly_z_threshold: float = 2.0    # |z| above this is anomalous
    feature_columns: list[str] = []     # Empty = auto-detect numeric columns
```

### PatternRecord

```python
class PatternRecord(BaseModel):
    """A single discovered pattern with evidence and provenance."""
    pattern_id: str                     # UUID
    pattern_type: str                   # "correlation" | "anomaly" | "temporal" | "cluster"
    description: str                    # Human-readable description
    evidence: dict[str, Any]            # Type-specific evidence (r, p, z, etc.)
    confidence: float                   # 0-1 confidence score
    session_ids: list[str]              # Sessions contributing to this pattern
    discovered_at: datetime             # UTC timestamp
```

### HypothesisInput

```python
class HypothesisInput(BaseModel):
    """Input to the hypothesis generator."""
    patterns: list[PatternRecord]       # Patterns to generate hypotheses from
    context: str = ""                   # Optional lab/experiment context
    constraints: list[str] = []         # Optional constraints on hypotheses
```

### HypothesisOutput

```python
class HypothesisOutput(BaseModel):
    """A generated hypothesis with metadata."""
    hypothesis_id: str                  # UUID
    statement: str                      # Human-readable hypothesis statement
    testable: bool                      # Whether this can be experimentally tested
    status: HypothesisStatus            # proposed / testing / confirmed / etc.
    confidence: float                   # 0-1 confidence from evidence strength
    required_experiments: list[str]     # What experiments would test this
    resource_estimate: str              # Human-readable resource estimate
    patterns_used: list[str]            # pattern_ids that support this hypothesis
```

### MiningResult

```python
class MiningResult(BaseModel):
    """Result of a full mining run."""
    config: MiningConfig                # Configuration used
    patterns: list[PatternRecord]       # All discovered patterns
    run_at: datetime                    # UTC timestamp of the run
    data_summary: dict[str, Any]        # Row count, column info, etc.
```

---

## Public Interfaces

### PatternMiner

Exhaustive pattern mining across experimental data. Uses numpy/scipy when available,
falls back to pure-Python implementations.

```python
class PatternMiner:
    def mine(
        self,
        data: list[dict[str, Any]],
        config: MiningConfig | None = None,
    ) -> MiningResult:
        """Run the full mining pipeline: correlations + anomalies + temporal.

        Returns MiningResult with all discovered patterns.
        If len(data) < config.min_sessions, returns empty patterns.
        Emits discovery.mining.completed event.
        """

    def find_correlations(
        self,
        data: list[dict[str, Any]],
        threshold: float = 0.5,
    ) -> list[PatternRecord]:
        """Find pairwise Pearson correlations among all numeric columns.

        For each pair (col_a, col_b) where |r| > threshold, creates a
        PatternRecord with evidence={r, p_value, col_a, col_b}.
        Emits discovery.pattern.found for each pattern.
        """

    def find_anomalies(
        self,
        data: list[dict[str, Any]],
        z_threshold: float = 2.0,
    ) -> list[PatternRecord]:
        """Detect anomalous rows via z-score analysis on numeric columns.

        For each numeric column, computes z-scores. Rows with |z| > threshold
        are grouped into a single PatternRecord per column.
        Emits discovery.pattern.found for each pattern.
        """

    def find_temporal_patterns(
        self,
        data: list[dict[str, Any]],
        time_col: str = "timestamp",
    ) -> list[PatternRecord]:
        """Detect temporal trends in numeric data sorted by time column.

        Splits data into first/second half and compares means. Significant
        differences (|diff| > std) indicate trends.
        Emits discovery.pattern.found for each pattern.
        """
```

### HypothesisGenerator

Template-based hypothesis generation from discovered patterns.
MVP implementation — no LLM calls, generates from pattern type templates.

```python
class HypothesisGenerator:
    def generate(
        self,
        input: HypothesisInput,
    ) -> list[HypothesisOutput]:
        """Generate hypotheses from discovered patterns.

        Template mapping:
        - correlation -> "X is correlated with Y (r=...). Hypothesis: changing X affects Y."
        - anomaly -> "Anomalous values in X at sessions [...]. Hypothesis: external factor."
        - temporal -> "Trend in X over time. Hypothesis: progressive change in X."
        - cluster -> "Distinct clusters found. Hypothesis: subpopulations exist."

        Emits discovery.hypothesis.created for each hypothesis.
        Returns list of HypothesisOutput ordered by confidence.
        """
```

---

## Events

| Event Name | Payload | Emitted By |
|---|---|---|
| `discovery.pattern.found` | `{pattern_id, pattern_type, confidence}` | PatternMiner.find_*() |
| `discovery.mining.completed` | `{pattern_count, run_at}` | PatternMiner.mine() |
| `discovery.hypothesis.created` | `{hypothesis_id, statement, confidence}` | HypothesisGenerator.generate() |

---

## Boundary Contracts

- All IDs are UUIDs (auto-generated by default)
- All timestamps are timezone-aware UTC (ISO 8601)
- Pydantic models validate at boundary (config submission, result creation)
- Events follow `{layer}.{module}.{action}` naming convention
- HypothesisStatus uses `core.schemas.HypothesisStatus` enum
- numpy/scipy are optional — imported with `try/except ImportError` and graceful fallback
- numpy int64/float64 are cast to native Python types before serialization
- `data` parameter is always `list[dict[str, Any]]` — each dict is one row/session
- Numeric columns are auto-detected unless `feature_columns` is set in config

## Error Conditions

| Condition | Behavior | Raised By |
|---|---|---|
| Insufficient data (< min_sessions) | Returns empty MiningResult (no error) | PatternMiner.mine() |
| No numeric columns found | Returns empty pattern list | PatternMiner.find_*() |
| Time column missing | Returns empty pattern list | PatternMiner.find_temporal_patterns() |
| Zero variance column | Skipped (no correlation/anomaly) | PatternMiner.find_correlations/anomalies() |
| numpy/scipy not installed | Falls back to pure-Python math | All methods |
| Empty pattern list input | Returns empty hypothesis list | HypothesisGenerator.generate() |

## Storage

- MVP: stateless — results returned directly, no persistence
- MiningResult and HypothesisOutput are Pydantic models, serializable to JSON
- Future: results written to Knowledge Graph (FindingNode) with provenance
- Future: persistent SQLite storage for mining history and trend analysis

## Acceptance Criteria

- [ ] MiningConfig correctly validates thresholds and column lists
- [ ] PatternMiner.find_correlations discovers Pearson correlations above threshold
- [ ] PatternMiner.find_anomalies detects z-score outliers
- [ ] PatternMiner.find_temporal_patterns detects trends in time-ordered data
- [ ] PatternMiner.mine runs all three methods and returns combined MiningResult
- [ ] mine() returns empty patterns when data < min_sessions
- [ ] HypothesisGenerator produces template-based hypotheses for each pattern type
- [ ] Each hypothesis has statement, testable flag, confidence, experiments, resources
- [ ] Events emitted: discovery.pattern.found, discovery.mining.completed, discovery.hypothesis.created
- [ ] numpy/scipy optional — graceful fallback to pure Python
- [ ] All schemas importable from `labclaw.discovery`
- [ ] All BDD scenarios pass
