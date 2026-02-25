Feature: Plugin Security
  The plugin loader enforces security constraints to prevent
  untrusted or unsafe plugins from loading at runtime.

  # ---------------------------------------------------------------------------
  # Allowlist enforcement
  # ---------------------------------------------------------------------------

  Scenario: Entry-point plugin in allowlist is loaded
    Given the plugin allowlist contains "trusted-plugin"
    When I discover entry-point plugin "trusted-plugin"
    Then 1 plugin is loaded
    And an infra.plugin.loaded event is emitted for "trusted-plugin"

  Scenario: Entry-point plugin not in allowlist is skipped
    Given the plugin allowlist contains "trusted-plugin"
    When I discover entry-point plugin "untrusted-plugin"
    Then 0 plugins are loaded
    And no infra.plugin.loaded event is emitted

  Scenario: Empty allowlist outside pytest denies all plugins
    Given no allowlist is configured
    And LABCLAW_PLUGIN_ALLOW_ALL is "0"
    And PYTEST_CURRENT_TEST is not set
    Then the allowlist check for "any-plugin" returns denied

  Scenario: LABCLAW_PLUGIN_ALLOW_ALL bypasses empty allowlist
    Given no allowlist is configured
    And LABCLAW_PLUGIN_ALLOW_ALL is "1"
    And PYTEST_CURRENT_TEST is not set
    Then the allowlist check for "any-plugin" returns permitted

  Scenario: Local plugin not in allowlist is skipped
    Given the plugin allowlist contains "only-this"
    And a local plugin directory with a plugin named "other_plugin"
    When I run local plugin discovery
    Then 0 plugins are loaded

  # ---------------------------------------------------------------------------
  # Disable switches
  # ---------------------------------------------------------------------------

  Scenario: Entry-point discovery disabled by flag
    Given LABCLAW_ENABLE_ENTRYPOINT_PLUGINS is "0"
    When I run entry-point discovery
    Then 0 plugins are loaded
    And the entry-point ep.load was never called

  Scenario: Local plugin discovery disabled by flag
    Given LABCLAW_ENABLE_LOCAL_PLUGINS is "0"
    And a local plugin directory with a valid plugin
    When I run local plugin discovery
    Then 0 plugins are loaded

  # ---------------------------------------------------------------------------
  # Secure directory validation
  # ---------------------------------------------------------------------------

  Scenario: World-writable plugin directory is rejected
    Given a local plugin directory that is world-writable
    When I run local plugin discovery
    Then 0 plugins are loaded
    And an infra.plugin.error event is emitted for that directory

  Scenario: Symlinked plugin directory is rejected
    Given a local plugin directory that is a symlink
    When I run local plugin discovery
    Then 0 plugins are loaded
    And an infra.plugin.error event is emitted for that directory

  Scenario: Plugin directory with failing uid lookup is insecure
    Given a plugin directory where os.getuid raises OSError
    Then _is_secure_plugin_dir returns False

  Scenario: Plugin directory with failing stat is insecure
    Given a plugin directory where path.stat raises OSError
    Then _is_secure_plugin_dir returns False

  # ---------------------------------------------------------------------------
  # Combined
  # ---------------------------------------------------------------------------

  Scenario: load_all with insecure local directory loads nothing from it
    Given a local plugin directory that is world-writable
    When I call load_all with that directory
    Then 0 plugins are loaded

  Scenario: load_all with no local directory loads nothing
    Given LABCLAW_ENABLE_ENTRYPOINT_PLUGINS is "0"
    When I call load_all with no local directory
    Then 0 plugins are loaded
