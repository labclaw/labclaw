Feature: LLM Providers (L5)
  LLM providers expose a uniform protocol for completions.
  Multiple backends are supported: Anthropic, OpenAI, and local (Ollama).

  Scenario: Create Anthropic provider with explicit key
    When I create an Anthropic provider with api_key "test-key-123"
    Then the provider model name is "claude-sonnet-4-6"

  Scenario: Create Anthropic provider with custom model
    When I create an Anthropic provider with model "claude-opus-4-6" and api_key "test-key"
    Then the provider model name is "claude-opus-4-6"

  Scenario: Anthropic provider raises error when no API key
    When I try to create an Anthropic provider without an API key
    Then a ValueError is raised for missing API key

  Scenario: Create OpenAI provider with explicit key
    When I create an OpenAI provider with api_key "sk-test-abc"
    Then the openai provider model name is "gpt-4o"

  Scenario: Create OpenAI provider with custom model
    When I create an OpenAI provider with model "gpt-4-turbo" and api_key "sk-test"
    Then the openai provider model name is "gpt-4-turbo"

  Scenario: OpenAI provider raises error when no API key
    When I try to create an OpenAI provider without an API key
    Then a ValueError is raised for missing API key

  Scenario: Create local provider with default settings
    When I create a local provider
    Then the local provider model name is "llama3.2"
    And the local provider base_url is "http://localhost:11434"

  Scenario: Create local provider with custom model and URL
    When I create a local provider with model "mistral" and url "http://192.168.1.10:11434"
    Then the local provider model name is "mistral"
    And the local provider base_url is "http://192.168.1.10:11434"

  Scenario: Mock provider generates a plain text completion
    Given a mock LLM provider returning "Analysis complete."
    When I call complete with prompt "Summarize data"
    Then the completion result is "Analysis complete."

  Scenario: Mock provider accepts system prompt without error
    Given a mock LLM provider returning "OK"
    When I call complete with prompt "Hello" and system "Be brief."
    Then the completion result is "OK"

  Scenario: LLMConfig default values are correct
    When I create a default LLMConfig
    Then the config provider is "anthropic"
    And the config model is "claude-sonnet-4-6"
    And the config temperature is 0.7

  Scenario: LLMConfig accepts custom values
    When I create an LLMConfig with provider "openai" and model "gpt-4o"
    Then the config provider is "openai"
    And the config model is "gpt-4o"

  Scenario: Mock provider satisfies LLMProvider protocol
    Given a mock LLM provider returning "test"
    Then the provider satisfies the LLMProvider protocol

  Scenario: Provider handles empty prompt gracefully
    Given a mock LLM provider with empty response
    When I call complete with an empty prompt
    Then the empty completion result is empty
