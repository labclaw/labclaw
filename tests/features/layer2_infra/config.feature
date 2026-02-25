Feature: Configuration
  LabClaw loads configuration from YAML files with sensible defaults.
  Settings can be overridden through configuration files.

  Scenario: Load default config returns a LabClawConfig object
    When I load the default configuration
    Then the config has a system section
    And the config has an api section
    And the config has an events section
    And the config has a graph section
    And the config has an edge section

  Scenario: Default config has expected API port
    When I load the default configuration
    Then the api port is 8000

  Scenario: Default config has expected database backend
    When I load the default configuration
    Then the graph backend is "sqlite"

  Scenario: Default config has expected events backend
    When I load the default configuration
    Then the events backend is "memory"

  Scenario: Default config has a system name
    When I load the default configuration
    Then the system name is "labclaw"

  Scenario: Default config has LLM settings
    When I load the default configuration
    Then the config has an llm section
    And the llm provider is "anthropic"

  Scenario: Default config has edge settings
    When I load the default configuration
    Then the edge watch_paths is a list

  Scenario: Load config from a custom YAML file
    Given a custom config file with api port 19999
    When I load the custom configuration
    Then the api port is 19999

  Scenario: Missing config file falls back to defaults
    When I load config from a nonexistent path
    Then the config has a system section
    And the api port is 8000
