Feature: Agent Execution
  Agents are LLM-backed assistants that can call registered tools
  to interact with the LabClaw system.

  Scenario: Agent responds to user question
    Given an agent runtime with a mock LLM provider
    And 3 built-in tools registered
    When the user asks "What patterns have been found?"
    Then the agent should return a text response
    And the message history should contain the exchange

  Scenario: Agent handles unknown tool call gracefully
    Given an agent runtime with no tools registered
    When the LLM returns a tool call for "nonexistent_tool"
    Then the tool result should indicate an error
    And available tools should be listed

  Scenario: Agent with multiple tools registered
    Given an agent runtime with a mock LLM provider
    When I register 5 tools on the agent
    Then the agent has 5 tools registered

  Scenario: Agent calls a tool and uses the result
    Given an agent runtime that calls "echo_tool" once then responds
    And the "echo_tool" is registered
    When the user asks "Call the echo tool"
    Then the agent should return a text response
    And the message history contains a tool result entry

  Scenario: Agent handles tool execution error gracefully
    Given an agent runtime that calls "failing_tool" once then responds
    And the "failing_tool" is registered and raises an exception
    When the user asks "Use the failing tool"
    Then the agent should return a text response
    And the tool result in history shows failure

  Scenario: Agent with empty tool list produces a response
    Given an agent runtime with a mock LLM provider
    When the user asks "Hello"
    Then the agent should return a text response

  Scenario: Agent message history tracks tool calls
    Given an agent runtime that calls "echo_tool" once then responds
    And the "echo_tool" is registered
    When the user asks "Please call echo_tool"
    Then the message history contains role "user"
    And the message history contains role "assistant"
    And the message history contains role "tool"

  Scenario: Agent uses custom system prompt
    Given an agent runtime with a mock LLM provider
    When the user asks "Explain the workflow" with system prompt "You are a concise assistant."
    Then the agent should return a text response

  Scenario: Agent handles empty user input
    Given an agent runtime with a mock LLM provider
    When the user sends an empty message
    Then the agent should return a text response

  Scenario: Agent tool returns complex structured data
    Given an agent runtime that calls "data_tool" once then responds
    And the "data_tool" is registered and returns structured data
    When the user asks "Fetch the data"
    Then the tool result in history contains structured data

  Scenario: Register duplicate tool name overwrites previous tool
    Given an agent runtime with a mock LLM provider
    When I register a tool named "alpha_tool" with description "First version"
    And I register a tool named "alpha_tool" with description "Second version"
    Then the agent has 1 tools registered
    And the "alpha_tool" description is "Second version"

  Scenario: Clear history resets conversation
    Given an agent runtime with a mock LLM provider
    And 3 built-in tools registered
    When the user asks "What patterns have been found?"
    And I clear the agent history
    Then the message history is empty
