# Cross-Cutting Graph Nodes Spec

**Layer:** Cross-cutting (knowledge graph schema)
**Design doc reference:** Section 4 (Lab Knowledge Graph), 4.1 (Entity Types), 4.2 (Experiment Hierarchy), 4.3 (Node Metadata)

## Purpose

Defines the 14 entity types that live in the Lab Knowledge Graph. Every entity in the system — people, devices, experiments, findings — is a graph node. This module provides the Pydantic models for all of them, plus the experiment hierarchy.

---

## Pydantic Schemas

### GraphNode Base

Every graph node carries:

```python
class GraphNode(BaseModel):
    """Base for all knowledge graph entities."""
    node_id: str           # UUID
    node_type: str         # Discriminator (e.g. "session", "subject")
    created_at: datetime   # UTC
    updated_at: datetime   # UTC
    created_by: str | None # operator_id or agent_id
    tags: list[str]        # Free-form tags
    metadata: dict[str, Any]  # Extension point
```

### 14 Entity Types

```
People       — PersonNode       — who, role, expertise, affiliation
Protocols    — ProtocolNode     — name, version, steps, pitfalls
Experiments  — ExperimentNode   — project, cohort/study arm, parameters
Subjects     — SubjectNode      — species, genotype, age, sex, surgical history
Sessions     — SessionNode      — date, rig, operator, duration
Trials       — TrialNode        — behavioral events within a session
Recordings   — RecordingNode    — data files (video, ephys, imaging)
Analyses     — AnalysisNode     — computed outputs (pose tracks, spike sorts)
Findings     — FindingNode      — conclusions, statistical results
Decisions    — DecisionNode     — why something was changed
Failures     — FailureNode      — what didn't work and why
Devices      — DeviceNode       — equipment status, calibration, quirks
Literature   — LiteratureNode   — papers, relevance to experiments
Assets       — AssetNode        — code, models, figures, datasets
```

### Experiment Hierarchy

```
ProjectNode (top-level)
  └── ExperimentNode (cohort/study arm)
        ├── SubjectNode (animal)
        └── SessionNode (one recording day)
              ├── TrialNode (behavioral event)
              ├── RecordingNode (data file)
              │     └── AnalysisNode (computed output)
              └── AnnotationNode (human or agent note — optional, not in 14)
```

### NWB Mapping

```
SessionNode    → NWBFile
SubjectNode    → NWBFile.subject
RecordingNode  → NWBFile.acquisition
AnalysisNode   → NWBFile.processing
```

---

## Public Interface

```python
def get_node_type(type_name: str) -> type[GraphNode]
    """Look up a node class by its type name string."""

NODE_TYPES: dict[str, type[GraphNode]]
    # Registry mapping type name → class
```

---

## Boundary Contracts

- All node IDs are UUIDs
- All timestamps are UTC
- `node_type` matches the class name's prefix (lowercase): `SessionNode` → `"session"`
- Node models are read/write — mutable after creation (via `updated_at`)
- Hierarchy is enforced by parent_id references, not nesting

## Acceptance Criteria

- [ ] All 14 node types importable from `jarvis_mesh.core.graph`
- [ ] Each node type has `node_type` auto-set to correct string
- [ ] `GraphNode` base provides `node_id`, `created_at`, `updated_at`, `created_by`, `tags`, `metadata`
- [ ] `get_node_type("session")` returns `SessionNode`
- [ ] All models serialize to JSON without errors
- [ ] Parent references use `parent_id: str | None` pattern
