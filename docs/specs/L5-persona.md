# L5 Persona Spec

**Design doc reference:** section 7 (Digital Staff Training & Promotion)

## Purpose

The persona subsystem manages human and digital staff within the lab.  Digital
members progress through a training pipeline (Intern -> Analyst -> Specialist)
based on benchmark performance.  Each member has a SOUL.md (identity) and
MEMORY.md (accumulated experience) managed via the Tier A memory backend.

Corrections are logged when mistakes are found, and promotion gates enforce
minimum competency thresholds before role advancement.

## Roles

Defined in `MemberRole` enum (`core/schemas.py`):

| Role | Type | Description |
|------|------|-------------|
| `pi` | Human | Principal Investigator |
| `postdoc` | Human | Postdoctoral researcher |
| `graduate` | Human | Graduate student |
| `undergraduate` | Human | Undergraduate student |
| `technician` | Human | Lab technician |
| `digital_intern` | Digital | Entry-level digital staff |
| `digital_analyst` | Digital | Mid-level digital staff |
| `digital_specialist` | Digital | Senior digital staff |

## Pydantic Schemas

All models live in `src/jarvis_mesh/persona/schemas.py`.

### MemberProfile

```python
class MemberProfile(BaseModel):
    member_id: str               # uuid4
    name: str
    role: MemberRole
    is_digital: bool
    expertise: list[str]
    created_at: datetime
    promoted_at: datetime | None
```

### BenchmarkResult

```python
class BenchmarkResult(BaseModel):
    member_id: str
    task_type: str
    score: float                 # 0.0 - 1.0
    completed_at: datetime
    details: dict[str, Any]
```

### CorrectionEntry

```python
class CorrectionEntry(BaseModel):
    member_id: str
    category: str
    detail: str
    corrected_by: str
    timestamp: datetime
```

### PromotionGate

```python
class PromotionGate(BaseModel):
    from_role: MemberRole
    to_role: MemberRole
    min_benchmarks: int
    min_avg_score: float
    requires_approval: bool
```

## Promotion Ladder

| From | To | Min Benchmarks | Min Avg Score | Requires Approval |
|------|----|---------------|---------------|-------------------|
| `digital_intern` | `digital_analyst` | 10 | 0.70 | No |
| `digital_analyst` | `digital_specialist` | 25 | 0.85 | Yes |

## Public Interface -- PersonaManager

```python
class PersonaManager:
    def create_member(name: str, role: MemberRole, is_digital: bool) -> MemberProfile
    def get_member(member_id: str) -> MemberProfile
    def record_benchmark(member_id: str, task_type: str, score: float, details: dict | None) -> BenchmarkResult
    def record_correction(member_id: str, category: str, detail: str, corrected_by: str) -> CorrectionEntry
    def check_promotion(member_id: str) -> PromotionGate | None
    def promote(member_id: str) -> MemberProfile
    def demote(member_id: str) -> MemberProfile
```

### Constraints

- `promote()` / `demote()` only change digital member roles along the ladder.
- Human members cannot be demoted below their actual role.
- `check_promotion()` returns the matching `PromotionGate` if the member meets
  all criteria, or `None` if not eligible.
- `demote()` raises `ValueError` for human members or members already at
  `digital_intern`.

## Events

| Event Name | Payload | Emitted When |
|------------|---------|-------------|
| `persona.member.created` | member_id, name, role | `create_member()` |
| `persona.benchmark.recorded` | member_id, task_type, score | `record_benchmark()` |
| `persona.correction.recorded` | member_id, category, corrected_by | `record_correction()` |
| `persona.member.promoted` | member_id, from_role, to_role | `promote()` |
| `persona.member.demoted` | member_id, from_role, to_role | `demote()` |

## Storage

- In-memory dicts for MVP (no SQLite persistence yet).
- Future: persist via Tier A markdown files and Tier B knowledge graph.
