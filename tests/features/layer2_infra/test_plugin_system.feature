Feature: Plugin System
  Plugins extend LabClaw with domain-specific devices, analysis,
  and knowledge. The registry manages discovery and retrieval.

  Scenario: Register and discover domain plugin
    Given a domain plugin with neuroscience metadata
    When the plugin is registered in the registry
    Then it should appear in the plugin list
    And it should be retrievable by type "domain"

  Scenario: Scaffold a new plugin project
    Given a target directory for the new plugin
    When I scaffold a plugin named "my-analyzer" of type "analysis"
    Then the directory structure should include pyproject.toml and __init__.py
    And the __init__.py should contain a create_plugin factory
