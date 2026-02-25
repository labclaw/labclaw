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

  Scenario: Register a device plugin
    Given a device plugin with camera metadata
    When the device plugin is registered in the registry
    Then it should appear in the plugin list
    And it should be retrievable by type "device"

  Scenario: Register an analysis plugin
    Given an analysis plugin with stats metadata
    When the analysis plugin is registered in the registry
    Then it should appear in the plugin list
    And it should be retrievable by type "analysis"

  Scenario: Get plugin by name
    Given a domain plugin with neuroscience metadata
    When the plugin is registered in the registry
    Then I can retrieve it by name "neuro-domain"

  Scenario: Get nonexistent plugin raises KeyError
    Given an empty plugin registry
    When I try to get plugin "does-not-exist"
    Then a plugin KeyError is raised

  Scenario: List plugins by type returns only matching type
    Given a domain plugin with neuroscience metadata
    And a device plugin with camera metadata
    When both plugins are registered in the same registry
    Then listing by type "domain" returns 1 plugin
    And listing by type "device" returns 1 plugin

  Scenario: Plugin metadata contains required fields
    Given a domain plugin with neuroscience metadata
    Then the plugin metadata has name "neuro-domain"
    And the plugin metadata has version "0.1.0"
    And the plugin metadata has a description
    And the plugin metadata has plugin_type "domain"

  Scenario: Registering duplicate plugin name raises ValueError
    Given a domain plugin with neuroscience metadata
    When the plugin is registered in the registry
    When I try to register the same plugin again
    Then a plugin ValueError is raised

  Scenario: Scaffold creates correct directory structure for device plugin
    Given a target directory for the new plugin
    When I scaffold a plugin named "my-device" of type "device"
    Then the directory structure should include pyproject.toml and __init__.py
    And the __init__.py should contain a create_plugin factory
    And the scaffolded plugin type is "device"

  Scenario: Scaffold creates correct directory structure for domain plugin
    Given a target directory for the new plugin
    When I scaffold a plugin named "my-domain" of type "domain"
    Then the directory structure should include pyproject.toml and __init__.py
    And the __init__.py should contain a create_plugin factory

  Scenario: Scaffold with invalid plugin type raises error
    Given a target directory for the new plugin
    When I try to scaffold a plugin named "bad-plugin" of type "invalid"
    Then a scaffold ValueError is raised

  Scenario: Plugin list is empty when no plugins registered
    Given an empty plugin registry
    Then the plugin list is empty
