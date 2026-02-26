"""BDD step definitions for L5 Persona (digital staff training & promotion).

Spec: docs/specs/L5-persona.md
Uses conftest fixtures: event_capture
"""

from __future__ import annotations

from pydantic import ValidationError
from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.core.schemas import MemberRole
from labclaw.persona.manager import PersonaManager
from labclaw.persona.schemas import BenchmarkResult, CorrectionEntry

# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("the persona manager is initialized", target_fixture="persona_mgr")
def persona_manager_initialized(event_capture: object) -> PersonaManager:
    """Create a PersonaManager and subscribe event capture to all persona events."""
    mgr = PersonaManager()
    for evt_name in [
        "persona.member.created",
        "persona.benchmark.recorded",
        "persona.correction.recorded",
        "persona.member.promoted",
        "persona.member.demoted",
    ]:
        event_registry.subscribe(evt_name, event_capture)  # type: ignore[arg-type]
    return mgr


# ---------------------------------------------------------------------------
# Member name -> id mapping (shared across steps in a scenario)
# ---------------------------------------------------------------------------


@given(
    parsers.parse('digital member "{name}" with role "{role}" exists'),
    target_fixture="member_map",
)
def digital_member_exists(
    persona_mgr: PersonaManager, name: str, role: str, member_map: dict | None = None
) -> dict[str, str]:
    """Create a digital member and store name->id mapping."""
    mapping = member_map or {}
    mr = MemberRole(role)
    profile = persona_mgr.create_member(name=name, role=mr, is_digital=True)
    mapping[name] = profile.member_id
    return mapping


@given(
    parsers.parse('human member "{name}" with role "{role}" exists'),
    target_fixture="member_map",
)
def human_member_exists(
    persona_mgr: PersonaManager, name: str, role: str, member_map: dict | None = None
) -> dict[str, str]:
    """Create a human member and store name->id mapping."""
    mapping = member_map or {}
    mr = MemberRole(role)
    profile = persona_mgr.create_member(name=name, role=mr, is_digital=False)
    mapping[name] = profile.member_id
    return mapping


# ---------------------------------------------------------------------------
# Create member
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I create a digital member "{name}" with role "{role}"'),
    target_fixture="member_map",
)
def create_digital_member(persona_mgr: PersonaManager, name: str, role: str) -> dict[str, str]:
    """Create a digital member and return name->id mapping."""
    mr = MemberRole(role)
    profile = persona_mgr.create_member(name=name, role=mr, is_digital=True)
    return {name: profile.member_id}


@when(
    parsers.parse('I create a human member "{name}" with role "{role}"'),
    target_fixture="member_map",
)
def create_human_member(persona_mgr: PersonaManager, name: str, role: str) -> dict[str, str]:
    """Create a human member and return name->id mapping."""
    mr = MemberRole(role)
    profile = persona_mgr.create_member(name=name, role=mr, is_digital=False)
    return {name: profile.member_id}


@then(parsers.parse('member "{name}" exists with role "{role}"'))
def check_member_exists_with_role(
    persona_mgr: PersonaManager, member_map: dict[str, str], name: str, role: str
) -> None:
    mid = member_map[name]
    profile = persona_mgr.get_member(mid)
    assert profile.role == MemberRole(role), f"Expected role {role!r}, got {profile.role.value!r}"


@then(parsers.parse('member "{name}" is digital'))
def check_member_is_digital(
    persona_mgr: PersonaManager, member_map: dict[str, str], name: str
) -> None:
    mid = member_map[name]
    profile = persona_mgr.get_member(mid)
    assert profile.is_digital, f"Expected member {name!r} to be digital"


@then(parsers.parse('member "{name}" is not digital'))
def check_member_is_not_digital(
    persona_mgr: PersonaManager, member_map: dict[str, str], name: str
) -> None:
    mid = member_map[name]
    profile = persona_mgr.get_member(mid)
    assert not profile.is_digital, f"Expected member {name!r} to not be digital"


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I record a benchmark for "{name}" with task "{task_type}" and score {score:g}'),
)
def record_benchmark(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    task_type: str,
    score: float,
) -> None:
    mid = member_map[name]
    persona_mgr.record_benchmark(mid, task_type, score)


@given(
    parsers.parse('"{name}" has {count:d} benchmarks with average score {avg:g}'),
)
def member_has_benchmarks(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    count: int,
    avg: float,
) -> None:
    """Seed the given number of benchmarks with the specified average score."""
    mid = member_map[name]
    for _ in range(count):
        persona_mgr.record_benchmark(mid, "seeded_task", avg)


@given(
    parsers.parse('"{name}" has a correction with category "{category}"'),
)
def member_has_correction(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    category: str,
) -> None:
    mid = member_map[name]
    persona_mgr.record_correction(mid, category, "seeded correction", corrected_by="test")


@then(parsers.parse('"{name}" has {count:d} benchmark recorded'))
def check_benchmark_count_singular(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    count: int,
) -> None:
    mid = member_map[name]
    benchmarks = persona_mgr.get_benchmarks(mid)
    assert len(benchmarks) == count, f"Expected {count} benchmarks, got {len(benchmarks)}"


@then(parsers.parse('"{name}" has {count:d} benchmarks recorded'))
def check_benchmark_count_plural(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    count: int,
) -> None:
    mid = member_map[name]
    benchmarks = persona_mgr.get_benchmarks(mid)
    assert len(benchmarks) == count, f"Expected {count} benchmarks, got {len(benchmarks)}"


@when(
    parsers.parse('I try to record an invalid benchmark for "{name}" with score {score:g}'),
    target_fixture="validation_error",
)
def try_record_invalid_benchmark(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    score: float,
) -> Exception | None:
    mid = member_map[name]
    try:
        persona_mgr.record_benchmark(mid, "test_task", score)
        return None
    except (ValidationError, ValueError) as exc:
        return exc


@then("a validation error is raised for the benchmark")
def check_validation_error(validation_error: Exception | None) -> None:
    assert validation_error is not None, "Expected a validation error but none was raised"
    assert isinstance(validation_error, (ValidationError, ValueError))


@when(
    parsers.parse('I get all benchmarks for "{name}"'),
    target_fixture="fetched_benchmarks",
)
def get_all_benchmarks(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
) -> list[BenchmarkResult]:
    mid = member_map[name]
    return persona_mgr.get_benchmarks(mid)


@then(parsers.parse('{n:d} benchmarks are returned for "{name}"'))
def check_benchmarks_returned(fetched_benchmarks: list[BenchmarkResult], n: int, name: str) -> None:
    assert len(fetched_benchmarks) == n, (
        f"Expected {n} benchmarks for {name!r}, got {len(fetched_benchmarks)}"
    )


# ---------------------------------------------------------------------------
# Corrections
# ---------------------------------------------------------------------------


@when(
    parsers.parse(
        'I record a correction for "{name}" with category "{category}" and detail "{detail}"'
    ),
)
def record_correction(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    category: str,
    detail: str,
) -> None:
    mid = member_map[name]
    persona_mgr.record_correction(mid, category, detail, corrected_by="test_user")


@when(
    parsers.parse(
        'I record a correction for "{name}" with category "{category}"'
        ' corrected by "{corrected_by}"'
    ),
    target_fixture="last_correction",
)
def record_correction_with_corrected_by(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    category: str,
    corrected_by: str,
) -> CorrectionEntry:
    mid = member_map[name]
    return persona_mgr.record_correction(mid, category, "test detail", corrected_by=corrected_by)


@then(parsers.parse('"{name}" has {count:d} correction recorded'))
def check_correction_count_singular(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    count: int,
) -> None:
    mid = member_map[name]
    corrections = persona_mgr.get_corrections(mid)
    assert len(corrections) == count, f"Expected {count} corrections, got {len(corrections)}"


@then(parsers.parse('"{name}" has {count:d} corrections recorded'))
def check_correction_count_plural(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    count: int,
) -> None:
    mid = member_map[name]
    corrections = persona_mgr.get_corrections(mid)
    assert len(corrections) == count, f"Expected {count} corrections, got {len(corrections)}"


@when(
    parsers.parse('I get all corrections for "{name}"'),
    target_fixture="fetched_corrections",
)
def get_all_corrections(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
) -> list[CorrectionEntry]:
    mid = member_map[name]
    return persona_mgr.get_corrections(mid)


@then(parsers.parse('{n:d} corrections are returned for "{name}"'))
def check_corrections_returned(
    fetched_corrections: list[CorrectionEntry], n: int, name: str
) -> None:
    assert len(fetched_corrections) == n, (
        f"Expected {n} corrections for {name!r}, got {len(fetched_corrections)}"
    )


@then(parsers.parse('the correction has corrected_by "{corrected_by}"'))
def check_correction_corrected_by(last_correction: CorrectionEntry, corrected_by: str) -> None:
    assert last_correction.corrected_by == corrected_by, (
        f"Expected corrected_by {corrected_by!r}, got {last_correction.corrected_by!r}"
    )


# ---------------------------------------------------------------------------
# Error paths for member/benchmark/correction lookups
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I try to get member with id "{member_id}"'),
    target_fixture="lookup_error",
)
def try_get_nonexistent_member(persona_mgr: PersonaManager, member_id: str) -> Exception | None:
    try:
        persona_mgr.get_member(member_id)
        return None
    except KeyError as exc:
        return exc


@then("a KeyError is raised")
def check_key_error_raised(lookup_error: Exception | None) -> None:
    assert isinstance(lookup_error, KeyError), f"Expected KeyError, got {type(lookup_error)}"


@when(
    parsers.parse('I try to get benchmarks for member id "{member_id}"'),
    target_fixture="lookup_error",
)
def try_get_benchmarks_for_nonexistent(
    persona_mgr: PersonaManager, member_id: str
) -> Exception | None:
    try:
        persona_mgr.get_benchmarks(member_id)
        return None
    except KeyError as exc:
        return exc


@when(
    parsers.parse('I try to get corrections for member id "{member_id}"'),
    target_fixture="lookup_error",
)
def try_get_corrections_for_nonexistent(
    persona_mgr: PersonaManager, member_id: str
) -> Exception | None:
    try:
        persona_mgr.get_corrections(member_id)
        return None
    except KeyError as exc:
        return exc


@when(
    parsers.parse('I try to record a benchmark for nonexistent member "{member_id}"'),
    target_fixture="lookup_error",
)
def try_record_benchmark_for_nonexistent(
    persona_mgr: PersonaManager, member_id: str
) -> Exception | None:
    try:
        persona_mgr.record_benchmark(member_id, "task", 0.5)
        return None
    except KeyError as exc:
        return exc


@when(
    parsers.parse('I try to record a correction for nonexistent member "{member_id}"'),
    target_fixture="lookup_error",
)
def try_record_correction_for_nonexistent(
    persona_mgr: PersonaManager, member_id: str
) -> Exception | None:
    try:
        persona_mgr.record_correction(member_id, "category", "detail", corrected_by="test")
        return None
    except KeyError as exc:
        return exc


@then("a KeyError is raised for member lookup")
def check_key_error_member_lookup(lookup_error: Exception | None) -> None:
    assert isinstance(lookup_error, KeyError), f"Expected KeyError, got {type(lookup_error)}"


# ---------------------------------------------------------------------------
# Promotion / Demotion
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I check promotion eligibility for "{name}"'),
    target_fixture="promo_gate",
)
def check_promotion_eligibility(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
) -> dict:
    mid = member_map[name]
    gate = persona_mgr.check_promotion(mid)
    return {"name": name, "gate": gate}


@then(parsers.parse('"{name}" is eligible for promotion to "{target_role}"'))
def check_eligible(promo_gate: dict, name: str, target_role: str) -> None:
    assert promo_gate["gate"] is not None, f"Expected {name!r} to be eligible"
    assert promo_gate["gate"].to_role == MemberRole(target_role), (
        f"Expected promotion to {target_role!r}, got {promo_gate['gate'].to_role.value!r}"
    )


@then(parsers.parse('"{name}" is not eligible for promotion'))
def check_not_eligible(promo_gate: dict, name: str) -> None:
    assert promo_gate["gate"] is None, (
        f"Expected {name!r} to NOT be eligible, but got gate: {promo_gate['gate']}"
    )


@when(parsers.parse('I promote "{name}"'))
def promote_member(persona_mgr: PersonaManager, member_map: dict[str, str], name: str) -> None:
    mid = member_map[name]
    persona_mgr.promote(mid)


@when(parsers.parse('I demote "{name}"'))
def demote_member(persona_mgr: PersonaManager, member_map: dict[str, str], name: str) -> None:
    mid = member_map[name]
    persona_mgr.demote(mid)


@when(
    parsers.parse('I try to demote "{name}"'),
    target_fixture="demotion_error",
)
def try_demote_member(
    persona_mgr: PersonaManager, member_map: dict[str, str], name: str
) -> Exception | None:
    mid = member_map[name]
    try:
        persona_mgr.demote(mid)
        return None
    except ValueError as exc:
        return exc


@when(
    parsers.parse('I try to promote "{name}"'),
    target_fixture="promotion_error",
)
def try_promote_member(
    persona_mgr: PersonaManager, member_map: dict[str, str], name: str
) -> Exception | None:
    mid = member_map[name]
    try:
        persona_mgr.promote(mid)
        return None
    except ValueError as exc:
        return exc


@then("a ValueError is raised for demotion")
def check_demotion_value_error(demotion_error: Exception | None) -> None:
    assert isinstance(demotion_error, ValueError), (
        f"Expected ValueError, got {type(demotion_error)}"
    )


@then("a ValueError is raised for promotion")
def check_promotion_value_error(promotion_error: Exception | None) -> None:
    assert isinstance(promotion_error, ValueError), (
        f"Expected ValueError, got {type(promotion_error)}"
    )


@then(parsers.parse('"{name}" has role "{role}"'))
def check_member_role(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    role: str,
) -> None:
    mid = member_map[name]
    profile = persona_mgr.get_member(mid)
    assert profile.role == MemberRole(role), f"Expected role {role!r}, got {profile.role.value!r}"


@then(parsers.parse('"{name}" has a promoted_at timestamp'))
def check_promoted_at_timestamp(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
) -> None:
    mid = member_map[name]
    profile = persona_mgr.get_member(mid)
    assert profile.promoted_at is not None, f"Expected {name!r} to have a promoted_at timestamp"
