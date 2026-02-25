Feature: Agent Tools (L5)
  Built-in agent tools are callable units that agents invoke to
  interact with the LabClaw system. Each tool has a name, description,
  parameter schema, and async execute method.

  Scenario: AgentTool has correct name and description
    Given an AgentTool named "my_tool" with description "Does something useful"
    Then the tool name is "my_tool"
    And the tool description is "Does something useful"

  Scenario: AgentTool parameter schema is accessible
    Given an AgentTool named "search_tool" with parameter schema "query"
    Then the tool has parameter "query" in its schema

  Scenario: AgentTool execute returns ToolResult on success
    Given an AgentTool that returns success
    When I execute the tool
    Then the result is a ToolResult with success true

  Scenario: AgentTool execute returns ToolResult on exception
    Given an AgentTool that raises an exception
    When I execute the tool
    Then the result is a ToolResult with success false
    And the result error message is not empty

  Scenario: ToolResult model has success and data fields
    When I create a ToolResult with success true and data "hello"
    Then the ToolResult success is true
    And the ToolResult data is "hello"

  Scenario: ToolResult with failure has error field
    When I create a ToolResult with success false and error "something broke"
    Then the ToolResult success is false
    And the ToolResult error is "something broke"

  Scenario: query_memory tool returns empty results when no memory root
    Given the query_memory built-in tool with no memory root
    When I execute query_memory with query "test pattern"
    Then the result is successful
    And the result data has empty results

  Scenario: device_status tool returns empty device list when no registry
    Given the device_status built-in tool with no device registry
    When I execute device_status
    Then the result is successful
    And the result data has empty device list

  Scenario: get_evolution_status tool returns empty cycles when no engine
    Given the get_evolution_status built-in tool with no engine
    When I execute get_evolution_status
    Then the result is successful
    And the result data has zero active cycles

  Scenario: search_findings tool returns empty results when no memory root
    Given the search_findings built-in tool with no memory root
    When I execute search_findings with query "hypothesis"
    Then the result is successful
    And the result data has empty results

  Scenario: get_evolution_status tool lists active cycles from real engine
    Given the get_evolution_status built-in tool with a running evolution engine
    When I execute get_evolution_status
    Then the result is successful
    And the result data has 1 active cycles

  Scenario: build_builtin_tools returns all 7 tools
    When I call build_builtin_tools with no dependencies
    Then 7 tools are returned
    And the tools include "query_memory"
    And the tools include "run_mining"
    And the tools include "hypothesize"
    And the tools include "device_status"
    And the tools include "propose_experiment"
    And the tools include "get_evolution_status"
    And the tools include "search_findings"

  Scenario: run_mining tool processes data rows
    Given the run_mining built-in tool
    When I execute run_mining with data rows
    Then the result is successful
    And the result data contains pattern_count

  Scenario: propose_experiment tool returns empty proposals without ranges
    Given the propose_experiment built-in tool
    When I execute propose_experiment with hypothesis_id "hyp-001" and no ranges
    Then the result is successful
    And the result data has empty proposals
