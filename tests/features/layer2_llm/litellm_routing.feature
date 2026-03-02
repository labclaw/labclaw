Feature: LiteLLM Multi-Model Routing (L2)
  LiteLLM provider enables multi-model routing with fallback chains,
  cost tracking, and rate limiting through a single unified interface.

  Scenario: Create LiteLLM provider with default model
    When I create a LiteLLM provider
    Then the litellm provider model name is "gpt-4o"

  Scenario: Create LiteLLM provider with custom model
    When I create a LiteLLM provider with model "claude-sonnet-4-6"
    Then the litellm provider model name is "claude-sonnet-4-6"

  Scenario: LiteLLM provider is registered in factory
    When I request a "litellm" provider from the factory
    Then the returned provider is a LiteLLMProvider

  Scenario: Basic completion returns text
    Given a mocked LiteLLM returning "Analysis complete."
    When I call litellm complete with prompt "Summarize data"
    Then the litellm result is "Analysis complete."

  Scenario: Completion with system prompt
    Given a mocked LiteLLM returning "system reply"
    When I call litellm complete with prompt "Hello" and system "Be brief."
    Then the litellm result is "system reply"

  Scenario: Fallback models are passed to LiteLLM
    Given a mocked LiteLLM with fallback models "gpt-4o-mini,claude-haiku-4-5"
    When I call litellm complete with prompt "test"
    Then the litellm call includes fallback models

  Scenario: Structured output returns validated model
    Given a mocked LiteLLM returning structured JSON '{"answer": "42", "score": 0.9}'
    When I call litellm complete_structured
    Then the structured result answer is "42"
    And the structured result score is 0.9

  Scenario: Timeout is propagated to LiteLLM
    Given a mocked LiteLLM with timeout 120
    When I call litellm complete with prompt "test"
    Then the litellm call has timeout 120

  Scenario: API error propagates as exception
    Given a mocked LiteLLM that raises an error
    When I call litellm complete expecting an error
    Then a litellm error is raised
