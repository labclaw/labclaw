"""BDD step definitions for L4 Memory (Tier A, B, C).

Spec: docs/specs/L4-memory.md
Uses conftest fixtures: tmp_path, event_capture
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.core.graph import PersonNode, ProjectNode
from labclaw.memory.knowledge_graph import TierBBackend
from labclaw.memory.markdown import MarkdownDoc, MemoryEntry, TierABackend

# ---------------------------------------------------------------------------
# Tier A — Background & fixtures
# ---------------------------------------------------------------------------


@given("the memory tier A backend is initialized", target_fixture="tier_a")
def tier_a_backend(tmp_path: Path, event_capture: object) -> TierABackend:
    """Create a TierABackend with a temp root and subscribe event capture."""
    root = tmp_path / "entities"
    root.mkdir()
    # Subscribe event_capture to all memory events
    for evt_name in ["memory.tier_a.created", "memory.tier_a.updated", "memory.search.executed"]:
        event_registry.subscribe(evt_name, event_capture)  # type: ignore[arg-type]
    return TierABackend(root=root)


# ---------------------------------------------------------------------------
# Tier A — SOUL.md write/read
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I create a SOUL for entity "{entity_id}" with name "{name}"'),
    target_fixture="write_result",
)
def create_soul(tier_a: TierABackend, entity_id: str, name: str) -> dict:
    """Write a SOUL.md for the given entity."""
    doc = MarkdownDoc(
        path=tier_a.root / entity_id / "SOUL.md",
        frontmatter={"name": name, "type": "entity"},
        content=f"# {name}\n\nIdentity document.",
    )
    tier_a.write_soul(entity_id, doc)
    return {"entity_id": entity_id, "name": name}


@when(
    parsers.parse('I request the SOUL for entity "{entity_id}"'),
    target_fixture="read_doc",
)
def request_soul(tier_a: TierABackend, entity_id: str) -> MarkdownDoc | Exception:
    """Read the SOUL.md; store exception if it fails."""
    try:
        return tier_a.read_soul(entity_id)
    except FileNotFoundError as exc:
        return exc


@then(parsers.parse('I receive a MarkdownDoc with frontmatter containing "{key}"'))
def check_frontmatter_has_key(read_doc: MarkdownDoc | Exception, key: str) -> None:
    assert isinstance(read_doc, MarkdownDoc), f"Expected MarkdownDoc, got {type(read_doc)}"
    assert key in read_doc.frontmatter, (
        f"Frontmatter missing key {key!r}: {read_doc.frontmatter}"
    )


@then(parsers.parse('the frontmatter "{key}" is "{value}"'))
def check_frontmatter_value(read_doc: MarkdownDoc, key: str, value: str) -> None:
    assert str(read_doc.frontmatter[key]) == value, (
        f"Expected frontmatter[{key!r}] == {value!r}, got {read_doc.frontmatter[key]!r}"
    )


@then("the content is valid markdown")
def check_content_is_markdown(read_doc: MarkdownDoc) -> None:
    assert isinstance(read_doc.content, str)
    assert len(read_doc.content) > 0, "Content should be non-empty"


# ---------------------------------------------------------------------------
# Tier A — MEMORY.md append
# ---------------------------------------------------------------------------


@given(
    parsers.parse('entity "{entity_id}" has a SOUL.md with name "{name}"'),
    target_fixture="setup_entity",
)
def entity_has_soul(tier_a: TierABackend, entity_id: str, name: str) -> str:
    """Create a SOUL.md for the entity as setup."""
    doc = MarkdownDoc(
        path=tier_a.root / entity_id / "SOUL.md",
        frontmatter={"name": name, "type": "member"},
        content=f"# {name}\n\nProfile.",
    )
    tier_a.write_soul(entity_id, doc)
    return entity_id


@when(
    parsers.parse('I append a memory entry with category "{category}" and detail "{detail}"'),
)
def append_memory_entry(
    tier_a: TierABackend, setup_entity: str, category: str, detail: str,
) -> None:
    """Append a memory entry to the current entity's MEMORY.md."""
    entry = MemoryEntry(
        timestamp=datetime.now(UTC),
        category=category,
        detail=detail,
    )
    tier_a.append_memory(setup_entity, entry)


@then(parsers.parse('the MEMORY.md for "{entity_id}" has {count:d} entries'))
def check_memory_entry_count(tier_a: TierABackend, entity_id: str, count: int) -> None:
    """Verify the number of ## sections in MEMORY.md."""
    doc = tier_a.read_memory(entity_id)
    # Count ## headers (each entry starts with ## timestamp)
    sections = [line for line in doc.content.split("\n") if line.startswith("## ")]
    assert len(sections) == count, (
        f"Expected {count} entries, found {len(sections)}: {sections}"
    )


# ---------------------------------------------------------------------------
# Tier A — Nonexistent entity
# ---------------------------------------------------------------------------


@then("a FileNotFoundError is raised")
def check_file_not_found(read_doc: MarkdownDoc | Exception) -> None:
    assert isinstance(read_doc, FileNotFoundError), (
        f"Expected FileNotFoundError, got {type(read_doc)}: {read_doc}"
    )


# ---------------------------------------------------------------------------
# Tier A — Search
# ---------------------------------------------------------------------------


@given(
    parsers.parse('entity "{entity_id}" has memory entries about "{topic}"'),
)
def entity_has_memory_about(tier_a: TierABackend, entity_id: str, topic: str) -> None:
    """Append memory entries about a topic."""
    entry = MemoryEntry(
        timestamp=datetime.now(UTC),
        category="note",
        detail=f"Detailed notes about {topic}. The {topic} is important for our experiments.",
    )
    tier_a.append_memory(entity_id, entry)


@when(
    parsers.parse('I search memory for "{query}"'),
    target_fixture="search_results",
)
def search_memory(tier_a: TierABackend, query: str) -> list:
    """Perform a search and store results."""
    return tier_a.search(query)


@then(parsers.parse('results contain entity "{entity_id}"'))
def check_results_contain_entity(search_results: list, entity_id: str) -> None:
    entity_ids = [r.entity_id for r in search_results]
    assert entity_id in entity_ids, (
        f"Expected entity {entity_id!r} in results, got {entity_ids}"
    )


@then("results are ranked by relevance score")
def check_results_ranked(search_results: list) -> None:
    assert len(search_results) > 0, "Expected at least one result"
    scores = [r.score for r in search_results]
    assert scores == sorted(scores, reverse=True), (
        f"Results not sorted by score descending: {scores}"
    )


# ---------------------------------------------------------------------------
# Tier B — Knowledge Graph
# ---------------------------------------------------------------------------

# Registry for node IDs created during tests
_kg_node_ids: dict[str, str] = {}


@given(
    "the knowledge graph backend is initialized",
    target_fixture="tier_b",
)
def kg_backend() -> TierBBackend:
    """Create a fresh TierBBackend."""
    _kg_node_ids.clear()
    return TierBBackend()


@when(
    parsers.parse('I add a person node with name "{name}"'),
    target_fixture="kg_added_node",
)
def add_person_node(tier_b: TierBBackend, name: str) -> PersonNode:
    node = PersonNode(name=name)
    tier_b.add_node(node)
    return node


@then(parsers.parse("the knowledge graph contains {count:d} node"))
@then(parsers.parse("the knowledge graph contains {count:d} nodes"))
def check_kg_node_count(tier_b: TierBBackend, count: int) -> None:
    assert tier_b.node_count == count, (
        f"Expected {count} nodes, got {tier_b.node_count}"
    )


@then("I can retrieve the node by its ID")
def check_retrieve_node(tier_b: TierBBackend, kg_added_node: PersonNode) -> None:
    retrieved = tier_b.get_node(kg_added_node.node_id)
    assert retrieved.node_id == kg_added_node.node_id


@given(
    parsers.parse('a person node "{label}" exists'),
)
def create_labeled_person(tier_b: TierBBackend, label: str) -> None:
    node = PersonNode(name=label)
    _kg_node_ids[label] = node.node_id
    tier_b.add_node(node)


@given(
    parsers.parse('a project node "{label}" exists'),
)
def create_labeled_project(tier_b: TierBBackend, label: str) -> None:
    node = ProjectNode(name=label)
    _kg_node_ids[label] = node.node_id
    tier_b.add_node(node)


@when(
    parsers.parse('I add an edge from "{src}" to "{tgt}" with relation "{rel}"'),
    target_fixture="kg_added_edge",
)
def add_edge(tier_b: TierBBackend, src: str, tgt: str, rel: str) -> object:
    return tier_b.add_edge(_kg_node_ids[src], _kg_node_ids[tgt], rel)


@given(
    parsers.parse('an edge from "{src}" to "{tgt}" with relation "{rel}" exists'),
)
def create_edge(tier_b: TierBBackend, src: str, tgt: str, rel: str) -> None:
    tier_b.add_edge(_kg_node_ids[src], _kg_node_ids[tgt], rel)


@then(parsers.parse("the knowledge graph contains {count:d} edge"))
@then(parsers.parse("the knowledge graph contains {count:d} edges"))
def check_kg_edge_count(tier_b: TierBBackend, count: int) -> None:
    assert tier_b.edge_count == count, (
        f"Expected {count} edges, got {tier_b.edge_count}"
    )


@then(parsers.parse('the edge has relation "{rel}"'))
def check_edge_relation(kg_added_edge: object, rel: str) -> None:
    from labclaw.memory.knowledge_graph import KGEdge
    assert isinstance(kg_added_edge, KGEdge)
    assert kg_added_edge.relation == rel


@given(parsers.parse("{count:d} person nodes exist"))
def create_n_persons(tier_b: TierBBackend, count: int) -> None:
    for i in range(count):
        node = PersonNode(name=f"Person {i}")
        tier_b.add_node(node)


@given(parsers.parse("{count:d} project nodes exist"))
def create_n_projects(tier_b: TierBBackend, count: int) -> None:
    for i in range(count):
        node = ProjectNode(name=f"Project {i}")
        tier_b.add_node(node)


@when(
    parsers.parse('I query nodes with type "{node_type}"'),
    target_fixture="kg_query_results",
)
def query_nodes_by_type(tier_b: TierBBackend, node_type: str) -> list:
    from labclaw.memory.knowledge_graph import KGQueryFilter
    return tier_b.query_nodes(KGQueryFilter(node_type=node_type))


@then(parsers.parse("I receive {count:d} nodes"))
def check_query_result_count(kg_query_results: list, count: int) -> None:
    assert len(kg_query_results) == count, (
        f"Expected {count} results, got {len(kg_query_results)}"
    )


@when(
    parsers.parse('I get neighbors of "{label}"'),
    target_fixture="kg_neighbors",
)
def get_neighbors(tier_b: TierBBackend, label: str) -> list:
    return tier_b.get_neighbors(_kg_node_ids[label])


@then(parsers.parse("I receive {count:d} neighbor"))
@then(parsers.parse("I receive {count:d} neighbors"))
def check_neighbor_count(kg_neighbors: list, count: int) -> None:
    assert len(kg_neighbors) == count, (
        f"Expected {count} neighbors, got {len(kg_neighbors)}"
    )


@then(parsers.parse('the neighbor is "{label}"'))
def check_neighbor_identity(kg_neighbors: list, label: str) -> None:
    neighbor_ids = [n[0].node_id for n in kg_neighbors]
    assert _kg_node_ids[label] in neighbor_ids


@given(parsers.parse('a person node with name "{name}" exists'))
def create_named_person(tier_b: TierBBackend, name: str) -> None:
    node = PersonNode(name=name)
    tier_b.add_node(node)


@when(
    parsers.parse('I search the knowledge graph for "{query}"'),
    target_fixture="kg_search_results",
)
def search_kg(tier_b: TierBBackend, query: str) -> list:
    return tier_b.search(query)


@then(parsers.parse('search results contain a node with name "{name}"'))
def check_kg_search_has_name(kg_search_results: list, name: str) -> None:
    node_data = [r.node.model_dump() for r in kg_search_results]
    names = [d.get("name", "") for d in node_data]
    assert name in names, f"Expected {name!r} in search results, got {names}"


@when(parsers.parse('I remove node "{label}"'))
def remove_node(tier_b: TierBBackend, label: str) -> None:
    tier_b.remove_node(_kg_node_ids[label])


@then(parsers.parse('adding another node with ID "{label}" raises ValueError'))
def check_duplicate_raises(tier_b: TierBBackend, label: str) -> None:
    node = PersonNode(name="duplicate", node_id=_kg_node_ids[label])
    with pytest.raises(ValueError):
        tier_b.add_node(node)


# ---------------------------------------------------------------------------
# Tier C — Shared Blocks stub
# ---------------------------------------------------------------------------


@given(
    "the shared blocks backend is not implemented",
    target_fixture="sb_error",
)
def sb_not_implemented() -> str:
    return "not_implemented"


@then("accessing shared blocks raises NotImplementedError")
def check_sb_not_implemented(sb_error: str) -> None:
    from labclaw.memory.shared_blocks import TierCBackend
    with pytest.raises(NotImplementedError):
        TierCBackend()
