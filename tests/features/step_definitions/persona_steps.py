"""BDD step definitions for L5 Persona (digital staff training & promotion).

Spec: docs/specs/L5-persona.md
Uses conftest fixtures: event_capture
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.core.schemas import MemberRole
from labclaw.persona.manager import PersonaManager

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


@then(parsers.parse('"{name}" has {count:d} benchmark recorded'))
def check_benchmark_count(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    count: int,
) -> None:
    mid = member_map[name]
    benchmarks = persona_mgr.get_benchmarks(mid)
    assert len(benchmarks) == count, f"Expected {count} benchmarks, got {len(benchmarks)}"


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


@then(parsers.parse('"{name}" has {count:d} correction recorded'))
def check_correction_count(
    persona_mgr: PersonaManager,
    member_map: dict[str, str],
    name: str,
    count: int,
) -> None:
    mid = member_map[name]
    corrections = persona_mgr.get_corrections(mid)
    assert len(corrections) == count, f"Expected {count} corrections, got {len(corrections)}"


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
