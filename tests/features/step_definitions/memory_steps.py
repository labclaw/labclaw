"""BDD step definitions for L4 Memory (Tier A, B, C).

Spec: docs/specs/L4-memory.md
Uses conftest fixtures: tmp_path, event_capture
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.core.graph import PersonNode, ProjectNode, ProtocolNode
from labclaw.memory.knowledge_graph import KGEdge, KGQueryFilter, TierBBackend
from labclaw.memory.markdown import MarkdownDoc, MemoryEntry, TierABackend

# ---------------------------------------------------------------------------
# Tier A — Background & fixtures
# ---------------------------------------------------------------------------


@given("the memory tier A backend is initialized", target_fixture="tier_a")
def tier_a_backend(tmp_path: Path, event_capture: object) -> TierABackend:
    """Create a TierABackend with a temp root and subscribe event capture."""
    root = tmp_path / "entities"
    root.mkdir()
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
    parsers.parse(
        'I create a SOUL for entity "{entity_id}" with role "{role}"'
        ' and status "{status}" and capabilities "{capabilities}"'
    ),
    target_fixture="write_result",
)
def create_soul_rich(
    tier_a: TierABackend,
    entity_id: str,
    role: str,
    status: str,
    capabilities: str,
) -> dict:
    """Write a SOUL.md with rich metadata."""
    doc = MarkdownDoc(
        path=tier_a.root / entity_id / "SOUL.md",
        frontmatter={
            "name": entity_id,
            "role": role,
            "status": status,
            "capabilities": capabilities.split(","),
        },
        content=f"# {entity_id}\n\nRich profile.",
    )
    tier_a.write_soul(entity_id, doc)
    return {"entity_id": entity_id}


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
    assert key in read_doc.frontmatter, f"Frontmatter missing key {key!r}: {read_doc.frontmatter}"


@then(parsers.parse('the frontmatter "{key}" is "{value}"'))
def check_frontmatter_value(read_doc: MarkdownDoc | Exception, key: str, value: str) -> None:
    assert isinstance(read_doc, MarkdownDoc)
    assert str(read_doc.frontmatter[key]) == value, (
        f"Expected frontmatter[{key!r}] == {value!r}, got {read_doc.frontmatter[key]!r}"
    )


@then("the content is valid markdown")
def check_content_is_markdown(read_doc: MarkdownDoc) -> None:
    assert isinstance(read_doc.content, str)
    assert len(read_doc.content) > 0, "Content should be non-empty"


# ---------------------------------------------------------------------------
# Tier A — SOUL.md update
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I update the SOUL for entity "{entity_id}" with name "{name}"'),
)
def update_soul(tier_a: TierABackend, entity_id: str, name: str) -> None:
    """Overwrite SOUL.md with a new name."""
    doc = MarkdownDoc(
        path=tier_a.root / entity_id / "SOUL.md",
        frontmatter={"name": name, "type": "entity"},
        content=f"# {name}\n\nUpdated identity.",
    )
    tier_a.write_soul(entity_id, doc)


# ---------------------------------------------------------------------------
# Tier A — List entities
# ---------------------------------------------------------------------------


@when("I list all entities", target_fixture="entity_list")
def list_all_entities(tier_a: TierABackend) -> list[str]:
    """Return sorted list of entity_ids that have a SOUL.md."""
    if not tier_a.root.exists():
        return []
    return sorted(
        d.name for d in tier_a.root.iterdir() if d.is_dir() and (d / "SOUL.md").exists()
    )


@then(parsers.parse('the entity list contains "{entity_id}"'))
def check_entity_list_contains(entity_list: list[str], entity_id: str) -> None:
    assert entity_id in entity_list, f"Expected {entity_id!r} in entity list: {entity_list}"


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
    tier_a: TierABackend,
    setup_entity: str,
    category: str,
    detail: str,
) -> None:
    """Append a memory entry to the current entity's MEMORY.md."""
    entry = MemoryEntry(
        timestamp=datetime.now(UTC),
        category=category,
        detail=detail,
    )
    tier_a.append_memory(setup_entity, entry)


@when(
    parsers.parse(
        'I append a memory entry for "{entity_id}" with category "{category}" and detail "{detail}"'
    ),
)
def append_memory_entry_for_entity(
    tier_a: TierABackend,
    entity_id: str,
    category: str,
    detail: str,
) -> None:
    """Append a memory entry directly to a named entity."""
    entry = MemoryEntry(
        timestamp=datetime.now(UTC),
        category=category,
        detail=detail,
    )
    tier_a.append_memory(entity_id, entry)


@then(parsers.parse('the MEMORY.md for "{entity_id}" has {count:d} entries'))
def check_memory_entry_count(tier_a: TierABackend, entity_id: str, count: int) -> None:
    """Verify the number of ## sections in MEMORY.md."""
    doc = tier_a.read_memory(entity_id)
    sections = [line for line in doc.content.split("\n") if line.startswith("## ")]
    assert len(sections) == count, f"Expected {count} entries, found {len(sections)}: {sections}"


@then("the memory entry contains a timestamp header")
def check_memory_entry_has_timestamp(tier_a: TierABackend, setup_entity: str) -> None:
    """Verify the MEMORY.md contains an ISO timestamp ## header."""
    doc = tier_a.read_memory(setup_entity)
    ts_headers = [line for line in doc.content.split("\n") if line.startswith("## ")]
    assert ts_headers, "No timestamp headers found in MEMORY.md"
    # Each header should look like "## 2026-02-24T..."
    header = ts_headers[0].strip()
    assert len(header) > 5, f"Timestamp header too short: {header!r}"


@then("the memory entries appear in chronological order")
def check_memory_entries_chronological(tier_a: TierABackend, setup_entity: str) -> None:
    """Verify the ## timestamp headers in MEMORY.md are in ascending order."""
    doc = tier_a.read_memory(setup_entity)
    ts_headers = [
        ln.replace("## ", "").strip()
        for ln in doc.content.split("\n")
        if ln.startswith("## ")
    ]
    assert len(ts_headers) >= 2, "Expected at least 2 entries for ordering check"
    assert ts_headers == sorted(ts_headers), (
        f"Entries not in chronological order: {ts_headers}"
    )


# ---------------------------------------------------------------------------
# Tier A — Read memory (error path)
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I request the memory for entity "{entity_id}"'),
    target_fixture="read_memory_result",
)
def request_memory(tier_a: TierABackend, entity_id: str) -> MarkdownDoc | Exception:
    """Read MEMORY.md; store exception if it fails."""
    try:
        return tier_a.read_memory(entity_id)
    except FileNotFoundError as exc:
        return exc


@then("a FileNotFoundError is raised for memory read")
def check_file_not_found_memory(read_memory_result: MarkdownDoc | Exception) -> None:
    assert isinstance(read_memory_result, FileNotFoundError), (
        f"Expected FileNotFoundError, got {type(read_memory_result)}: {read_memory_result}"
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
    assert entity_id in entity_ids, f"Expected entity {entity_id!r} in results, got {entity_ids}"


@then("results are ranked by relevance score")
def check_results_ranked(search_results: list) -> None:
    assert len(search_results) > 0, "Expected at least one result"
    scores = [r.score for r in search_results]
    assert scores == sorted(scores, reverse=True), (
        f"Results not sorted by score descending: {scores}"
    )


@then("memory search results are empty")
def check_memory_search_empty(search_results: list) -> None:
    assert search_results == [], f"Expected empty results, got {search_results}"


# ---------------------------------------------------------------------------
# Tier B — Knowledge Graph
# ---------------------------------------------------------------------------

# Registry for node IDs created during tests — keyed by label
_kg_node_ids: dict[str, str] = {}
# Track last-added edge for removal tests
_kg_last_edge: dict[str, KGEdge] = {}


@given(
    "the knowledge graph backend is initialized",
    target_fixture="tier_b",
)
def kg_backend() -> TierBBackend:
    """Create a fresh TierBBackend."""
    _kg_node_ids.clear()
    _kg_last_edge.clear()
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
    assert tier_b.node_count == count, f"Expected {count} nodes, got {tier_b.node_count}"


@then("I can retrieve the node by its ID")
def check_retrieve_node(tier_b: TierBBackend, kg_added_node: PersonNode) -> None:
    retrieved = tier_b.get_node(kg_added_node.node_id)
    assert retrieved.node_id == kg_added_node.node_id


@then("the added node has a created_at timestamp")
def check_node_has_timestamp(tier_b: TierBBackend, kg_added_node: PersonNode) -> None:
    assert kg_added_node.created_at is not None
    assert isinstance(kg_added_node.created_at, datetime)


# ---- look up nonexistent node ----


@when(
    parsers.parse('I look up node id "{node_id}"'),
    target_fixture="kg_lookup_exc",
)
def lookup_node_by_raw_id(tier_b: TierBBackend, node_id: str) -> Exception | None:
    try:
        tier_b.get_node(node_id)
        return None
    except KeyError as exc:
        return exc


@then("a KeyError is raised for node lookup")
def check_key_error_node_lookup(kg_lookup_exc: Exception | None) -> None:
    assert isinstance(kg_lookup_exc, KeyError), (
        f"Expected KeyError, got {type(kg_lookup_exc)}: {kg_lookup_exc}"
    )


# ---- list all nodes ----


@when("I list all nodes", target_fixture="kg_all_nodes")
def list_all_kg_nodes(tier_b: TierBBackend) -> list:
    return tier_b.all_nodes()


@then(parsers.parse("I receive a list of {count:d} nodes"))
def check_all_nodes_count(kg_all_nodes: list, count: int) -> None:
    assert len(kg_all_nodes) == count, f"Expected {count} nodes in list, got {len(kg_all_nodes)}"


# ---- graph stats ----


@then(parsers.parse("the graph node count is {count:d}"))
def check_graph_node_count(tier_b: TierBBackend, count: int) -> None:
    assert tier_b.node_count == count, f"Expected node_count={count}, got {tier_b.node_count}"


@then(parsers.parse("the graph edge count is {count:d}"))
def check_graph_edge_count(tier_b: TierBBackend, count: int) -> None:
    assert tier_b.edge_count == count, f"Expected edge_count={count}, got {tier_b.edge_count}"


# ---- labeled node creation (given steps) ----


@given(parsers.parse('a person node "{label}" exists'))
def create_labeled_person(tier_b: TierBBackend, label: str) -> None:
    node = PersonNode(name=label)
    _kg_node_ids[label] = node.node_id
    tier_b.add_node(node)


@given(parsers.parse('a project node "{label}" exists'))
def create_labeled_project(tier_b: TierBBackend, label: str) -> None:
    node = ProjectNode(name=label)
    _kg_node_ids[label] = node.node_id
    tier_b.add_node(node)


# ---- add edge ----


@when(
    parsers.parse('I add an edge from "{src}" to "{tgt}" with relation "{rel}"'),
    target_fixture="kg_added_edge",
)
def add_edge(tier_b: TierBBackend, src: str, tgt: str, rel: str) -> object:
    edge = tier_b.add_edge(_kg_node_ids[src], _kg_node_ids[tgt], rel)
    _kg_last_edge["last"] = edge
    return edge


@when(
    parsers.parse('I add another edge from "{src}" to "{tgt}" with relation "{rel}"'),
)
def add_another_edge(tier_b: TierBBackend, src: str, tgt: str, rel: str) -> None:
    edge = tier_b.add_edge(_kg_node_ids[src], _kg_node_ids[tgt], rel)
    _kg_last_edge["last"] = edge


@when(
    parsers.parse(
        'I add an edge from "{src}" to "{tgt}" with relation "{rel}"'
        ' and property "{prop_key}" equal to "{prop_val}"'
    ),
    target_fixture="kg_added_edge",
)
def add_edge_with_property(
    tier_b: TierBBackend,
    src: str,
    tgt: str,
    rel: str,
    prop_key: str,
    prop_val: str,
) -> KGEdge:
    edge = tier_b.add_edge(_kg_node_ids[src], _kg_node_ids[tgt], rel, {prop_key: prop_val})
    _kg_last_edge["last"] = edge
    return edge


@given(
    parsers.parse('an edge from "{src}" to "{tgt}" with relation "{rel}" exists'),
)
def create_edge(tier_b: TierBBackend, src: str, tgt: str, rel: str) -> None:
    edge = tier_b.add_edge(_kg_node_ids[src], _kg_node_ids[tgt], rel)
    _kg_last_edge["last"] = edge


# ---- edge assertions ----


@then(parsers.parse("the knowledge graph contains {count:d} edge"))
@then(parsers.parse("the knowledge graph contains {count:d} edges"))
def check_kg_edge_count(tier_b: TierBBackend, count: int) -> None:
    assert tier_b.edge_count == count, f"Expected {count} edges, got {tier_b.edge_count}"


@then(parsers.parse('the edge has relation "{rel}"'))
def check_edge_relation(kg_added_edge: object, rel: str) -> None:
    assert isinstance(kg_added_edge, KGEdge)
    assert kg_added_edge.relation == rel


@then(parsers.parse('the edge property "{key}" equals "{value}"'))
def check_edge_property(kg_added_edge: KGEdge, key: str, value: str) -> None:
    assert isinstance(kg_added_edge, KGEdge)
    assert key in kg_added_edge.properties, (
        f"Edge missing property {key!r}: {kg_added_edge.properties}"
    )
    assert str(kg_added_edge.properties[key]) == value, (
        f"Expected property {key!r}={value!r}, got {kg_added_edge.properties[key]!r}"
    )


@then(parsers.parse('there are {count:d} edges between "{src}" and "{tgt}"'))
def check_edges_between(tier_b: TierBBackend, count: int, src: str, tgt: str) -> None:
    edges = tier_b.get_edges_between(_kg_node_ids[src], _kg_node_ids[tgt])
    assert len(edges) == count, (
        f"Expected {count} edges between {src!r} and {tgt!r}, got {len(edges)}"
    )


# ---- invalid edge creation ----


@when(
    parsers.parse('I try to add an edge from "{src_label}" to "{tgt_label}" with relation "{rel}"'),
    target_fixture="kg_edge_exc",
)
def try_add_invalid_edge(
    tier_b: TierBBackend, src_label: str, tgt_label: str, rel: str
) -> Exception | None:
    """Attempt to add edge where one or both nodes may not exist."""
    src_id = _kg_node_ids.get(src_label, src_label)
    tgt_id = _kg_node_ids.get(tgt_label, tgt_label)
    try:
        tier_b.add_edge(src_id, tgt_id, rel)
        return None
    except KeyError as exc:
        return exc


@then("a KeyError is raised for edge creation")
def check_key_error_edge_creation(kg_edge_exc: Exception | None) -> None:
    assert isinstance(kg_edge_exc, KeyError), (
        f"Expected KeyError, got {type(kg_edge_exc)}: {kg_edge_exc}"
    )


# ---- remove edge ----


@when("I remove the last added edge")
def remove_last_edge(tier_b: TierBBackend) -> None:
    edge = _kg_last_edge["last"]
    tier_b.remove_edge(edge.edge_id)


@when(
    parsers.parse('I try to remove edge id "{edge_id}"'),
    target_fixture="kg_remove_edge_exc",
)
def try_remove_nonexistent_edge(tier_b: TierBBackend, edge_id: str) -> Exception | None:
    try:
        tier_b.remove_edge(edge_id)
        return None
    except KeyError as exc:
        return exc


@then("a KeyError is raised for edge removal")
def check_key_error_edge_removal(kg_remove_edge_exc: Exception | None) -> None:
    assert isinstance(kg_remove_edge_exc, KeyError), (
        f"Expected KeyError, got {type(kg_remove_edge_exc)}: {kg_remove_edge_exc}"
    )


# ---- query by type ----


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
    return tier_b.query_nodes(KGQueryFilter(node_type=node_type))


@then(parsers.parse("I receive {count:d} nodes"))
def check_query_result_count(kg_query_results: list, count: int) -> None:
    assert len(kg_query_results) == count, f"Expected {count} results, got {len(kg_query_results)}"


# ---- get neighbors ----


@when(
    parsers.parse('I get neighbors of "{label}"'),
    target_fixture="kg_neighbors",
)
def get_neighbors(tier_b: TierBBackend, label: str) -> list:
    return tier_b.get_neighbors(_kg_node_ids[label])


@when(
    parsers.parse('I get outgoing neighbors of "{label}"'),
    target_fixture="kg_neighbors",
)
def get_outgoing_neighbors(tier_b: TierBBackend, label: str) -> list:
    return tier_b.get_neighbors(_kg_node_ids[label], direction="outgoing")


@then(parsers.parse("I receive {count:d} neighbor"))
@then(parsers.parse("I receive {count:d} neighbors"))
def check_neighbor_count(kg_neighbors: list, count: int) -> None:
    assert len(kg_neighbors) == count, f"Expected {count} neighbors, got {len(kg_neighbors)}"


@then(parsers.parse('the neighbor is "{label}"'))
def check_neighbor_identity(kg_neighbors: list, label: str) -> None:
    neighbor_ids = [n[0].node_id for n in kg_neighbors]
    assert _kg_node_ids[label] in neighbor_ids


# ---- get edges between ----


@when(
    parsers.parse('I get all edges between "{src}" and "{tgt}"'),
    target_fixture="kg_edges_between",
)
def get_edges_between(tier_b: TierBBackend, src: str, tgt: str) -> list:
    return tier_b.get_edges_between(_kg_node_ids[src], _kg_node_ids[tgt])


@then(parsers.parse("I receive {count:d} edge between them"))
@then(parsers.parse("I receive {count:d} edges between them"))
def check_edges_between_count(kg_edges_between: list, count: int) -> None:
    assert len(kg_edges_between) == count, (
        f"Expected {count} edges, got {len(kg_edges_between)}"
    )


# ---- search ----


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


@then("the search result list is empty")
def check_kg_search_empty(kg_search_results: list) -> None:
    assert kg_search_results == [], f"Expected empty search results, got {kg_search_results}"


# ---- remove node ----


@when(parsers.parse('I remove node "{label}"'))
def remove_node(tier_b: TierBBackend, label: str) -> None:
    tier_b.remove_node(_kg_node_ids[label])


@when(
    parsers.parse('I try to remove node "{label}"'),
    target_fixture="kg_remove_node_exc",
)
def try_remove_nonexistent_node(tier_b: TierBBackend, label: str) -> Exception | None:
    node_id = _kg_node_ids.get(label, label)
    try:
        tier_b.remove_node(node_id)
        return None
    except KeyError as exc:
        return exc


@then("a KeyError is raised for node removal")
def check_key_error_node_removal(kg_remove_node_exc: Exception | None) -> None:
    assert isinstance(kg_remove_node_exc, KeyError), (
        f"Expected KeyError, got {type(kg_remove_node_exc)}: {kg_remove_node_exc}"
    )


# ---- duplicate node ----


@then(parsers.parse('adding another node with ID "{label}" raises ValueError'))
def check_duplicate_raises(tier_b: TierBBackend, label: str) -> None:
    node = PersonNode(name="duplicate", node_id=_kg_node_ids[label])
    with pytest.raises(ValueError):
        tier_b.add_node(node)


# ---------------------------------------------------------------------------
# Tier C — Shared Blocks stub
# ---------------------------------------------------------------------------


@given(
    "the shared blocks backend is implemented",
    target_fixture="sb_status",
)
def sb_implemented() -> str:
    return "implemented"


@then("accessing shared blocks succeeds")
def check_sb_implemented(sb_status: str) -> None:
    from labclaw.memory.shared_blocks import TierCBackend

    backend = TierCBackend()
    assert backend is not None


# ---------------------------------------------------------------------------
# Tier C — Shared Blocks full API (in-memory mode)
# ---------------------------------------------------------------------------


@given("the shared blocks backend is initialized in memory mode", target_fixture="tier_c")
def tier_c_backend() -> object:
    """Return a fresh in-memory TierCBackend (no SQLite file)."""
    from labclaw.memory.shared_blocks import TierCBackend

    return TierCBackend()


def _run(coro: object) -> Any:
    """Run a coroutine synchronously (no existing event loop in tests)."""
    return asyncio.new_event_loop().run_until_complete(coro)  # type: ignore[arg-type]


@when("I list all block keys", target_fixture="tier_c_keys")
def list_block_keys(tier_c: object) -> list[str]:
    from labclaw.memory.shared_blocks import TierCBackend

    assert isinstance(tier_c, TierCBackend)
    return _run(tier_c.list_blocks())


@then("the block key list is empty")
def check_block_key_list_empty(tier_c_keys: list[str]) -> None:
    assert tier_c_keys == [], f"Expected empty key list, got {tier_c_keys}"


@then(parsers.parse('the block key list contains "{key}"'))
def check_block_key_list_contains(tier_c_keys: list[str], key: str) -> None:
    assert key in tier_c_keys, f"Expected {key!r} in key list: {tier_c_keys}"


@when(parsers.parse('I set block "{key}" to value "{value}"'))
def set_block_simple(tier_c: object, key: str, value: str) -> None:
    from labclaw.memory.shared_blocks import TierCBackend

    assert isinstance(tier_c, TierCBackend)
    _run(tier_c.set_block(key, {"value": value}))


@when(
    parsers.parse('I set block "{key}" to complex value with key "{field}" and value "{val}"'),
)
def set_block_complex(tier_c: object, key: str, field: str, val: str) -> None:
    from labclaw.memory.shared_blocks import TierCBackend

    assert isinstance(tier_c, TierCBackend)
    _run(tier_c.set_block(key, {field: val, "nested": {"x": 1}}))


@when(parsers.parse('I get block "{key}"'), target_fixture="tier_c_block")
def get_block(tier_c: object, key: str) -> dict | None:
    from labclaw.memory.shared_blocks import TierCBackend

    assert isinstance(tier_c, TierCBackend)
    return _run(tier_c.get_block(key))


@then(parsers.parse('the block value contains "{value}"'))
def check_block_value(tier_c_block: dict | None, value: str) -> None:
    assert tier_c_block is not None, "Expected block, got None"
    assert tier_c_block.get("value") == value, (
        f"Expected value={value!r}, got {tier_c_block.get('value')!r}"
    )


@then("the block result is None")
def check_block_is_none(tier_c_block: dict | None) -> None:
    assert tier_c_block is None, f"Expected None, got {tier_c_block}"


@then(parsers.parse('the block complex value has key "{field}" equal to "{val}"'))
def check_block_complex_value(tier_c_block: dict | None, field: str, val: str) -> None:
    assert tier_c_block is not None, "Expected block, got None"
    assert tier_c_block.get(field) == val, (
        f"Expected {field!r}={val!r}, got {tier_c_block.get(field)!r}"
    )


@when(parsers.parse('I delete block "{key}"'), target_fixture="tier_c_delete_result")
def delete_block(tier_c: object, key: str) -> bool:
    from labclaw.memory.shared_blocks import TierCBackend

    assert isinstance(tier_c, TierCBackend)
    return _run(tier_c.delete_block(key))


@then("the delete result is False")
def check_delete_false(tier_c_delete_result: bool) -> None:
    assert tier_c_delete_result is False, f"Expected False, got {tier_c_delete_result}"


@then("the delete result is True")
def check_delete_true(tier_c_delete_result: bool) -> None:
    assert tier_c_delete_result is True, f"Expected True, got {tier_c_delete_result}"


@then(parsers.parse('block "{key}" exists in the backend'))
def check_block_exists(tier_c: object, key: str) -> None:
    from labclaw.memory.shared_blocks import TierCBackend

    assert isinstance(tier_c, TierCBackend)
    result = _run(tier_c.get_block(key))
    assert result is not None, f"Expected block {key!r} to exist, got None"


@then(parsers.parse('block "{key}" does not exist in the backend'))
def check_block_not_exists(tier_c: object, key: str) -> None:
    from labclaw.memory.shared_blocks import TierCBackend

    assert isinstance(tier_c, TierCBackend)
    result = _run(tier_c.get_block(key))
    assert result is None, f"Expected block {key!r} to not exist, got {result}"


# ---------------------------------------------------------------------------
# Hybrid Search — step definitions
# ---------------------------------------------------------------------------


@given(
    "the hybrid search engine is initialized with tier A and tier B",
    target_fixture="search_engine",
)
def hybrid_search_engine(tmp_path: Path) -> object:
    """Set up HybridSearchEngine with both tier A and tier B backends."""
    from labclaw.memory.knowledge_graph import TierBBackend
    from labclaw.memory.markdown import TierABackend
    from labclaw.memory.search import HybridSearchConfig, HybridSearchEngine

    root = tmp_path / "hybrid_entities"
    root.mkdir()
    tier_a = TierABackend(root=root)
    tier_b = TierBBackend()
    config = HybridSearchConfig(tier_a_weight=1.0, tier_b_weight=1.0)
    engine = HybridSearchEngine(tier_a=tier_a, tier_b=tier_b, config=config)
    # Attach backends for use in given steps
    engine._test_tier_a = tier_a  # type: ignore[attr-defined]
    engine._test_tier_b = tier_b  # type: ignore[attr-defined]
    return engine


@given(parsers.parse('a markdown entity "{entity_id}" with SOUL content "{content}"'))
def add_markdown_entity(search_engine: object, entity_id: str, content: str) -> None:
    """Add a SOUL.md to the Tier A backend of the search engine."""
    tier_a: TierABackend = search_engine._test_tier_a  # type: ignore[attr-defined]
    doc = MarkdownDoc(
        path=tier_a.root / entity_id / "SOUL.md",
        frontmatter={"name": entity_id},
        content=f"# {entity_id}\n\n{content}",
    )
    tier_a.write_soul(entity_id, doc)


@given(parsers.parse('a knowledge graph node with name "{name}"'))
def add_kg_node(search_engine: object, name: str) -> None:
    """Add a PersonNode to the Tier B backend of the search engine."""
    tier_b: TierBBackend = search_engine._test_tier_b  # type: ignore[attr-defined]
    node = PersonNode(name=name)
    tier_b.add_node(node)


@given(parsers.parse("{count:d} markdown entities with content \"{content}\""))
def add_multiple_markdown_entities(search_engine: object, count: int, content: str) -> None:
    tier_a: TierABackend = search_engine._test_tier_a  # type: ignore[attr-defined]
    for i in range(count):
        entity_id = f"bulk-entity-{i}"
        doc = MarkdownDoc(
            path=tier_a.root / entity_id / "SOUL.md",
            frontmatter={"name": entity_id},
            content=f"# {entity_id}\n\n{content}",
        )
        tier_a.write_soul(entity_id, doc)


@when("I run a hybrid search with an empty query", target_fixture="hybrid_results")
def run_hybrid_search_empty(search_engine: object) -> list:
    from labclaw.memory.search import HybridSearchEngine, HybridSearchQuery

    assert isinstance(search_engine, HybridSearchEngine)
    q = HybridSearchQuery(text="")
    return search_engine.search(q)


@when(
    parsers.parse('I run a hybrid search for "{query}"'),
    target_fixture="hybrid_results",
)
def run_hybrid_search(search_engine: object, query: str) -> list:
    from labclaw.memory.search import HybridSearchEngine, HybridSearchQuery

    assert isinstance(search_engine, HybridSearchEngine)
    q = HybridSearchQuery(text=query)
    return search_engine.search(q)


@when(
    parsers.parse('I run a hybrid search for "{query}" with limit {limit:d}'),
    target_fixture="hybrid_results",
)
def run_hybrid_search_with_limit(search_engine: object, query: str, limit: int) -> list:
    from labclaw.memory.search import HybridSearchEngine, HybridSearchQuery

    assert isinstance(search_engine, HybridSearchEngine)
    q = HybridSearchQuery(text=query, limit=limit)
    return search_engine.search(q)


@when(
    parsers.parse('I run a hybrid search for "{query}" filtered by entity "{entity_id}"'),
    target_fixture="hybrid_results",
)
def run_hybrid_search_with_filter(search_engine: object, query: str, entity_id: str) -> list:
    from labclaw.memory.search import HybridSearchEngine, HybridSearchQuery

    assert isinstance(search_engine, HybridSearchEngine)
    q = HybridSearchQuery(text=query, entity_filter=entity_id)
    return search_engine.search(q)


@when(
    parsers.parse('I run a hybrid search for "{query}" in tier "{tier}" only'),
    target_fixture="hybrid_results",
)
def run_hybrid_search_tier_only(search_engine: object, query: str, tier: str) -> list:
    from labclaw.memory.search import HybridSearchEngine, HybridSearchQuery

    assert isinstance(search_engine, HybridSearchEngine)
    q = HybridSearchQuery(text=query, tiers=[tier])
    return search_engine.search(q)


@then(parsers.parse('the hybrid results contain source tier "{tier}"'))
def check_hybrid_results_contain_tier(hybrid_results: list, tier: str) -> None:
    tiers = [r.source_tier for r in hybrid_results]
    assert tier in tiers, f"Expected tier {tier!r} in results, got tiers: {tiers}"


@then("hybrid results are ranked by score descending")
def check_hybrid_ranked(hybrid_results: list) -> None:
    assert len(hybrid_results) > 0, "Expected at least one result"
    scores = [r.score for r in hybrid_results]
    assert scores == sorted(scores, reverse=True), (
        f"Hybrid results not sorted descending: {scores}"
    )


@then("the hybrid result list is empty")
def check_hybrid_empty(hybrid_results: list) -> None:
    assert hybrid_results == [], f"Expected empty hybrid results, got {hybrid_results}"


@then(parsers.parse("I receive at most {count:d} hybrid results"))
def check_hybrid_result_limit(hybrid_results: list, count: int) -> None:
    assert len(hybrid_results) <= count, (
        f"Expected at most {count} results, got {len(hybrid_results)}"
    )


@then(parsers.parse('all hybrid results have entity id "{entity_id}"'))
def check_hybrid_results_entity_filter(hybrid_results: list, entity_id: str) -> None:
    assert len(hybrid_results) > 0, "Expected at least one result"
    for r in hybrid_results:
        assert r.entity_id == entity_id, (
            f"Expected entity_id={entity_id!r}, got {r.entity_id!r}"
        )


# ---------------------------------------------------------------------------
# SQLite Tier B Backend — step definitions
# ---------------------------------------------------------------------------

# Per-scenario SQLite state: node label → node_id, last edge
_sq_node_ids: dict[str, str] = {}
_sq_last_edge: dict[str, str] = {}  # "last" → edge_id


@given("the SQLite Tier B backend is initialized", target_fixture="sqlite_tier_b")
def sqlite_tier_b_backend(tmp_path: Path) -> object:
    """Create and initialize a SQLiteTierBBackend with a temp db."""
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    _sq_node_ids.clear()
    _sq_last_edge.clear()
    db_path = tmp_path / "tier_b_test.db"
    backend = SQLiteTierBBackend(db_path=db_path)
    _run(backend.init_db())
    return backend


@then(parsers.parse("the SQLite backend has {count:d} nodes"))
def check_sqlite_node_count(sqlite_tier_b: object, count: int) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    actual = _run(sqlite_tier_b.node_count())
    assert actual == count, f"Expected {count} SQLite nodes, got {actual}"


@then(parsers.parse("the SQLite backend has {count:d} edges"))
def check_sqlite_edge_count(sqlite_tier_b: object, count: int) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    actual = _run(sqlite_tier_b.edge_count())
    assert actual == count, f"Expected {count} SQLite edges, got {actual}"


@when(parsers.parse('I add a person node "{label}" to the SQLite backend'))
def add_person_sqlite(sqlite_tier_b: object, label: str) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    node = PersonNode(name=label)
    _sq_node_ids[label] = node.node_id
    _run(sqlite_tier_b.add_node(node))


@when(
    parsers.parse(
        'I add a protocol node "{label}" with name "{name}" to SQLite'
    ),
)
def add_protocol_sqlite(sqlite_tier_b: object, label: str, name: str) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    node = ProtocolNode(name=name)
    _sq_node_ids[label] = node.node_id
    _run(sqlite_tier_b.add_node(node))


@then(parsers.parse('I can retrieve node "{label}" from the SQLite backend'))
def check_retrieve_sqlite_node(sqlite_tier_b: object, label: str) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    node_id = _sq_node_ids[label]
    node = _run(sqlite_tier_b.get_node(node_id))
    assert node.node_id == node_id


@then(parsers.parse('adding "{label}" again to the SQLite backend raises ValueError'))
def check_sqlite_duplicate_raises(sqlite_tier_b: object, label: str) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    node = PersonNode(name=label, node_id=_sq_node_ids[label])
    with pytest.raises(ValueError):
        _run(sqlite_tier_b.add_node(node))


@when(
    parsers.parse('I look up "{label}" in the SQLite backend'),
    target_fixture="sqlite_lookup_exc",
)
def lookup_sqlite_node(sqlite_tier_b: object, label: str) -> Exception | None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    node_id = _sq_node_ids.get(label, label)
    try:
        _run(sqlite_tier_b.get_node(node_id))
        return None
    except KeyError as exc:
        return exc


@then("a KeyError is raised for SQLite node lookup")
def check_sqlite_key_error_node(sqlite_lookup_exc: Exception | None) -> None:
    assert isinstance(sqlite_lookup_exc, KeyError), (
        f"Expected KeyError, got {type(sqlite_lookup_exc)}: {sqlite_lookup_exc}"
    )


@when(parsers.parse('I remove node "{label}" from the SQLite backend'))
def remove_sqlite_node(sqlite_tier_b: object, label: str) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    node_id = _sq_node_ids[label]
    _run(sqlite_tier_b.remove_node(node_id))


@when(
    parsers.parse('I try to remove "{label}" from the SQLite backend'),
    target_fixture="sqlite_remove_exc",
)
def try_remove_sqlite_node(sqlite_tier_b: object, label: str) -> Exception | None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    node_id = _sq_node_ids.get(label, label)
    try:
        _run(sqlite_tier_b.remove_node(node_id))
        return None
    except KeyError as exc:
        return exc


@then("a KeyError is raised for SQLite node removal")
def check_sqlite_key_error_remove(sqlite_remove_exc: Exception | None) -> None:
    assert isinstance(sqlite_remove_exc, KeyError), (
        f"Expected KeyError, got {type(sqlite_remove_exc)}: {sqlite_remove_exc}"
    )


@when(parsers.parse('I update node "{label}" name to "{name}" in the SQLite backend'))
def update_sqlite_node(sqlite_tier_b: object, label: str, name: str) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    node_id = _sq_node_ids[label]
    _run(sqlite_tier_b.update_node(node_id, name=name))


@then(parsers.parse('retrieving "{label}" from SQLite has name "{name}"'))
def check_sqlite_node_name(sqlite_tier_b: object, label: str, name: str) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    node_id = _sq_node_ids[label]
    node = _run(sqlite_tier_b.get_node(node_id))
    actual = getattr(node, "name", None)
    assert actual == name, f"Expected name={name!r}, got {actual!r}"


@given(parsers.parse('SQLite node "{label}" exists'))
def create_sqlite_node(sqlite_tier_b: object, label: str) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    node = PersonNode(name=label)
    _sq_node_ids[label] = node.node_id
    _run(sqlite_tier_b.add_node(node))


@when(
    parsers.parse('I add an edge from "{src}" to "{tgt}" with relation "{rel}" in SQLite'),
)
def add_sqlite_edge(sqlite_tier_b: object, src: str, tgt: str, rel: str) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    edge = _run(sqlite_tier_b.add_edge(_sq_node_ids[src], _sq_node_ids[tgt], rel))
    _sq_last_edge["last"] = edge.edge_id


@given(
    parsers.parse('a SQLite edge from "{src}" to "{tgt}" with relation "{rel}" exists'),
)
def create_sqlite_edge(sqlite_tier_b: object, src: str, tgt: str, rel: str) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    edge = _run(sqlite_tier_b.add_edge(_sq_node_ids[src], _sq_node_ids[tgt], rel))
    _sq_last_edge["last"] = edge.edge_id


@when("I remove the SQLite edge")
def remove_sqlite_edge(sqlite_tier_b: object) -> None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    edge_id = _sq_last_edge["last"]
    _run(sqlite_tier_b.remove_edge(edge_id))


@when(
    parsers.parse('I try to remove SQLite edge "{edge_id}"'),
    target_fixture="sqlite_edge_remove_exc",
)
def try_remove_sqlite_edge(sqlite_tier_b: object, edge_id: str) -> Exception | None:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    try:
        _run(sqlite_tier_b.remove_edge(edge_id))
        return None
    except KeyError as exc:
        return exc


@then("a KeyError is raised for SQLite edge removal")
def check_sqlite_key_error_edge(sqlite_edge_remove_exc: Exception | None) -> None:
    assert isinstance(sqlite_edge_remove_exc, KeyError), (
        f"Expected KeyError, got {type(sqlite_edge_remove_exc)}: {sqlite_edge_remove_exc}"
    )


@when(
    parsers.parse('I query SQLite nodes by type "{node_type}"'),
    target_fixture="sqlite_query_results",
)
def query_sqlite_nodes_by_type(sqlite_tier_b: object, node_type: str) -> list:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    return _run(sqlite_tier_b.query_nodes(KGQueryFilter(node_type=node_type)))


@then(parsers.parse("I receive {count:d} SQLite nodes"))
def check_sqlite_query_count(sqlite_query_results: list, count: int) -> None:
    assert len(sqlite_query_results) == count, (
        f"Expected {count} SQLite nodes, got {len(sqlite_query_results)}"
    )


@when(
    parsers.parse('I search the SQLite backend for "{query}"'),
    target_fixture="sqlite_search_results",
)
def search_sqlite_backend(sqlite_tier_b: object, query: str) -> list:
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    return _run(sqlite_tier_b.search(query))


@then(parsers.parse('the SQLite search results contain a node named "{name}"'))
def check_sqlite_search_has_name(sqlite_search_results: list, name: str) -> None:
    names = [getattr(r.node, "name", "") for r in sqlite_search_results]
    assert name in names, f"Expected {name!r} in SQLite search results, got {names}"


@when("I close and reopen the SQLite backend at the same path")
def reopen_sqlite_backend(sqlite_tier_b: object) -> None:
    """Close the current SQLite connection and reopen it."""
    from labclaw.memory.sqlite_backend import SQLiteTierBBackend

    assert isinstance(sqlite_tier_b, SQLiteTierBBackend)
    _run(sqlite_tier_b.close())
    sqlite_tier_b._db = None
    # Reuse same object; re-init opens the existing db file
    _run(sqlite_tier_b.init_db())
