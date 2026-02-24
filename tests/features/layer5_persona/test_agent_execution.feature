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
