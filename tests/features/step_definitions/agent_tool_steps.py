"""BDD step definitions for Agent Tools (L5 Persona).

Tests AgentTool, ToolResult, and built-in tool factories.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pytest_bdd import given, parsers, then, when

from labclaw.agents.tools import AgentTool, ToolResult, build_builtin_tools

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_async(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _success_fn(**kwargs: Any) -> ToolResult:
    return ToolResult(success=True, data="success")


async def _failing_fn(**kwargs: Any) -> ToolResult:
    raise RuntimeError("Tool failure")


async def _data_rows_fn(data_rows: list[dict[str, Any]] | None = None, **kwargs: Any) -> ToolResult:
    return ToolResult(success=True, data={"pattern_count": 0, "patterns": []})


async def _propose_experiment_fn(
    hypothesis_id: str = "",
    numeric_ranges: dict | None = None,
    **kwargs: Any,
) -> ToolResult:
    return ToolResult(success=True, data={"hypothesis_id": hypothesis_id, "proposals": []})


# ---------------------------------------------------------------------------
# Given steps — AgentTool construction
# ---------------------------------------------------------------------------


@given(
    parsers.parse('an AgentTool named "{name}" with description "{description}"'),
    target_fixture="agent_tool",
)
def make_agent_tool_with_description(name: str, description: str) -> AgentTool:
    return AgentTool(name=name, description=description, fn=_success_fn)


@given(
    parsers.parse('an AgentTool named "{name}" with parameter schema "{param}"'),
    target_fixture="agent_tool",
)
def make_agent_tool_with_schema(name: str, param: str) -> AgentTool:
    return AgentTool(
        name=name,
        description="Tool with schema",
        fn=_success_fn,
        parameters_schema={param: {"type": "string"}},
    )


@given("an AgentTool that returns success", target_fixture="agent_tool")
def make_success_agent_tool() -> AgentTool:
    return AgentTool(name="success_tool", description="Always succeeds", fn=_success_fn)


@given("an AgentTool that raises an exception", target_fixture="agent_tool")
def make_failing_agent_tool() -> AgentTool:
    return AgentTool(name="failing_tool", description="Always fails", fn=_failing_fn)


# ---------------------------------------------------------------------------
# Given steps — built-in tools with dependencies
# ---------------------------------------------------------------------------


@given("the query_memory built-in tool with no memory root", target_fixture="builtin_tool")
def query_memory_tool_no_root() -> AgentTool:
    tools = build_builtin_tools(memory_root=None)
    return next(t for t in tools if t.name == "query_memory")


@given("the device_status built-in tool with no device registry", target_fixture="builtin_tool")
def device_status_tool_no_registry() -> AgentTool:
    tools = build_builtin_tools(device_registry=None)
    return next(t for t in tools if t.name == "device_status")


@given(
    "the get_evolution_status built-in tool with no engine",
    target_fixture="builtin_tool",
)
def evolution_status_tool_no_engine() -> AgentTool:
    tools = build_builtin_tools(evolution_engine=None)
    return next(t for t in tools if t.name == "get_evolution_status")


@given(
    "the search_findings built-in tool with no memory root",
    target_fixture="builtin_tool",
)
def search_findings_tool_no_root() -> AgentTool:
    tools = build_builtin_tools(memory_root=None)
    return next(t for t in tools if t.name == "search_findings")


@given(
    "the get_evolution_status built-in tool with a running evolution engine",
    target_fixture="builtin_tool",
)
def evolution_status_tool_with_engine() -> AgentTool:
    from labclaw.core.schemas import EvolutionTarget
    from labclaw.evolution.engine import EvolutionEngine
    from labclaw.evolution.schemas import EvolutionCandidate, FitnessScore

    engine = EvolutionEngine()
    baseline = FitnessScore(
        target=EvolutionTarget.ANALYSIS_PARAMS,
        metrics={"accuracy": 0.80},
    )
    candidate = EvolutionCandidate(
        target=EvolutionTarget.ANALYSIS_PARAMS,
        description="test candidate",
        config_diff={"x": 1},
    )
    engine.start_cycle(candidate, baseline)

    tools = build_builtin_tools(evolution_engine=engine)
    return next(t for t in tools if t.name == "get_evolution_status")


@given("the run_mining built-in tool", target_fixture="builtin_tool")
def run_mining_tool() -> AgentTool:
    tools = build_builtin_tools()
    return next(t for t in tools if t.name == "run_mining")


@given("the propose_experiment built-in tool", target_fixture="builtin_tool")
def propose_experiment_tool() -> AgentTool:
    tools = build_builtin_tools()
    return next(t for t in tools if t.name == "propose_experiment")


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("I execute the tool", target_fixture="tool_exec_result")
def execute_tool(agent_tool: AgentTool) -> ToolResult:
    return _run_async(agent_tool.execute())


@when(
    parsers.parse('I execute query_memory with query "{query}"'),
    target_fixture="tool_exec_result",
)
def execute_query_memory(builtin_tool: AgentTool, query: str) -> ToolResult:
    return _run_async(builtin_tool.execute(query=query))


@when("I execute device_status", target_fixture="tool_exec_result")
def execute_device_status(builtin_tool: AgentTool) -> ToolResult:
    return _run_async(builtin_tool.execute())


@when("I execute get_evolution_status", target_fixture="tool_exec_result")
def execute_evolution_status(builtin_tool: AgentTool) -> ToolResult:
    return _run_async(builtin_tool.execute())


@when(
    parsers.parse('I execute search_findings with query "{query}"'),
    target_fixture="tool_exec_result",
)
def execute_search_findings(builtin_tool: AgentTool, query: str) -> ToolResult:
    return _run_async(builtin_tool.execute(query=query))


@when("I execute run_mining with data rows", target_fixture="tool_exec_result")
def execute_run_mining(builtin_tool: AgentTool) -> ToolResult:
    data_rows = [
        {"session_id": "s1", "metric_a": 1.0, "metric_b": 2.0},
        {"session_id": "s2", "metric_a": 1.1, "metric_b": 2.1},
    ]
    return _run_async(builtin_tool.execute(data_rows=data_rows))


@when(
    parsers.parse('I execute propose_experiment with hypothesis_id "{hyp_id}" and no ranges'),
    target_fixture="tool_exec_result",
)
def execute_propose_experiment_no_ranges(builtin_tool: AgentTool, hyp_id: str) -> ToolResult:
    return _run_async(builtin_tool.execute(hypothesis_id=hyp_id))


@when(
    "I call build_builtin_tools with no dependencies",
    target_fixture="builtin_tools_list",
)
def call_build_builtin_tools() -> list[AgentTool]:
    return build_builtin_tools()


@when(
    parsers.parse('I create a ToolResult with success true and data "{data}"'),
    target_fixture="tool_result_obj",
)
def create_tool_result_success(data: str) -> ToolResult:
    return ToolResult(success=True, data=data)


@when(
    parsers.parse('I create a ToolResult with success false and error "{error}"'),
    target_fixture="tool_result_obj",
)
def create_tool_result_failure(error: str) -> ToolResult:
    return ToolResult(success=False, error=error)


# ---------------------------------------------------------------------------
# Then steps — AgentTool introspection
# ---------------------------------------------------------------------------


@then(parsers.parse('the tool name is "{name}"'))
def check_tool_name(agent_tool: AgentTool, name: str) -> None:
    assert agent_tool.name == name, f"Expected tool name {name!r}, got {agent_tool.name!r}"


@then(parsers.parse('the tool description is "{description}"'))
def check_tool_description(agent_tool: AgentTool, description: str) -> None:
    assert agent_tool.description == description, (
        f"Expected description {description!r}, got {agent_tool.description!r}"
    )


@then(parsers.parse('the tool has parameter "{param}" in its schema'))
def check_tool_has_parameter(agent_tool: AgentTool, param: str) -> None:
    assert param in agent_tool.parameters_schema, (
        f"Expected parameter {param!r} in schema, got {list(agent_tool.parameters_schema)}"
    )


# ---------------------------------------------------------------------------
# Then steps — ToolResult
# ---------------------------------------------------------------------------


@then("the result is a ToolResult with success true")
def check_result_success(tool_exec_result: ToolResult) -> None:
    assert isinstance(tool_exec_result, ToolResult)
    assert tool_exec_result.success is True, f"Expected success=True, got {tool_exec_result}"


@then("the result is a ToolResult with success false")
def check_result_failure(tool_exec_result: ToolResult) -> None:
    assert isinstance(tool_exec_result, ToolResult)
    assert tool_exec_result.success is False, f"Expected success=False, got {tool_exec_result}"


@then("the result error message is not empty")
def check_result_error_not_empty(tool_exec_result: ToolResult) -> None:
    assert tool_exec_result.error, f"Expected non-empty error, got {tool_exec_result.error!r}"


@then("the result is successful")
def check_builtin_result_success(tool_exec_result: ToolResult) -> None:
    assert tool_exec_result.success is True, (
        f"Expected success=True, got error={tool_exec_result.error!r}"
    )


@then("the result data has empty results")
def check_result_data_empty_results(tool_exec_result: ToolResult) -> None:
    data = tool_exec_result.data
    results = data.get("results", None) if isinstance(data, dict) else None
    assert results is not None, f"Expected 'results' key in data, got {data}"
    assert results == [], f"Expected empty results list, got {results}"


@then("the result data has empty device list")
def check_result_data_empty_devices(tool_exec_result: ToolResult) -> None:
    data = tool_exec_result.data
    devices = data.get("devices", None) if isinstance(data, dict) else None
    assert devices is not None, f"Expected 'devices' key in data, got {data}"
    assert devices == [], f"Expected empty device list, got {devices}"


@then("the result data has zero active cycles")
def check_result_data_zero_cycles(tool_exec_result: ToolResult) -> None:
    data = tool_exec_result.data
    assert isinstance(data, dict), f"Expected dict data, got {type(data)}"
    # No engine configured: returns {"cycles": [], "note": ...}
    # Engine configured: returns {"active_cycle_count": N, "cycles": [...]}
    cycles = data.get("cycles", None)
    count = data.get("active_cycle_count", None)
    if cycles is not None and count is None:
        assert cycles == [], f"Expected empty cycles list, got {cycles}"
    elif count is not None:
        assert count == 0, f"Expected active_cycle_count=0, got {count}"
    else:
        raise AssertionError(f"Expected 'cycles' or 'active_cycle_count' in data, got {data}")


@then(parsers.parse("the result data has {n:d} active cycles"))
def check_result_data_n_active_cycles(tool_exec_result: ToolResult, n: int) -> None:
    data = tool_exec_result.data
    assert isinstance(data, dict), f"Expected dict data, got {type(data)}"
    count = data.get("active_cycle_count", -1)
    assert count == n, f"Expected active_cycle_count={n}, got {count}"


@then("the result data has empty proposals")
def check_result_data_empty_proposals(tool_exec_result: ToolResult) -> None:
    data = tool_exec_result.data
    assert isinstance(data, dict), f"Expected dict data, got {data}"
    proposals = data.get("proposals", None)
    assert proposals is not None, f"Expected 'proposals' key in data, got {data}"
    assert proposals == [], f"Expected empty proposals, got {proposals}"


@then("the result data contains pattern_count")
def check_result_data_has_pattern_count(tool_exec_result: ToolResult) -> None:
    data = tool_exec_result.data
    assert isinstance(data, dict), f"Expected dict data, got {data}"
    assert "pattern_count" in data, f"Expected 'pattern_count' in data, got {list(data)}"


# ---------------------------------------------------------------------------
# Then steps — build_builtin_tools
# ---------------------------------------------------------------------------


@then(parsers.parse("{n:d} tools are returned"))
def check_builtin_tools_count(builtin_tools_list: list[AgentTool], n: int) -> None:
    assert len(builtin_tools_list) == n, f"Expected {n} tools, got {len(builtin_tools_list)}"


@then(parsers.parse('the tools include "{tool_name}"'))
def check_builtin_tools_include(builtin_tools_list: list[AgentTool], tool_name: str) -> None:
    names = [t.name for t in builtin_tools_list]
    assert tool_name in names, f"Expected tool {tool_name!r} in list, got {names}"


# ---------------------------------------------------------------------------
# Then steps — ToolResult model
# ---------------------------------------------------------------------------


@then("the ToolResult success is true")
def check_tool_result_success_true(tool_result_obj: ToolResult) -> None:
    assert tool_result_obj.success is True


@then("the ToolResult success is false")
def check_tool_result_success_false(tool_result_obj: ToolResult) -> None:
    assert tool_result_obj.success is False


@then(parsers.parse('the ToolResult data is "{data}"'))
def check_tool_result_data(tool_result_obj: ToolResult, data: str) -> None:
    assert str(tool_result_obj.data) == data, (
        f"Expected data {data!r}, got {tool_result_obj.data!r}"
    )


@then(parsers.parse('the ToolResult error is "{error}"'))
def check_tool_result_error(tool_result_obj: ToolResult, error: str) -> None:
    assert tool_result_obj.error == error, (
        f"Expected error {error!r}, got {tool_result_obj.error!r}"
    )
