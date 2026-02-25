Feature: Miscellaneous Infrastructure Hardening
  Atomic writes, daemon plugin trust, MCP security, and CLI reproduce command
  are hardened against common failure modes and path traversal.

  # -----------------------------------------------------------------------
  # Recovery — atomic writes
  # -----------------------------------------------------------------------

  Scenario: Atomic state write uses os.replace for crash safety
    Given a state recovery instance with a temporary directory
    When I save state with cycle_count 7
    Then the state file exists and contains cycle_count 7
    And no leftover .tmp files remain

  Scenario: State written atomically survives a simulated crash mid-write
    Given a state recovery instance with a saved state containing cycle_count 3
    When a leftover .tmp file is present from a previous interrupted write
    And I load the state
    Then the loaded state contains cycle_count 3

  # -----------------------------------------------------------------------
  # Daemon — plugin path trust
  # -----------------------------------------------------------------------

  Scenario: Daemon accepts a plugin directory inside the trusted root
    Given a daemon instance with data_dir inside the trusted memory root
    When the daemon resolves the local plugin directory
    Then the returned path is inside the trusted root

  Scenario: Daemon rejects a plugin directory outside the trusted root
    Given a daemon instance with data_dir outside the trusted memory root
    When the daemon resolves the local plugin directory
    Then the returned path is None

  # -----------------------------------------------------------------------
  # MCP server — security
  # -----------------------------------------------------------------------

  Scenario: MCP server can be created without raising
    When I call create_server
    Then an MCP FastMCP instance is returned

  Scenario: MCP discover tool returns a no-data message when session chronicle is empty
    Given the MCP server is created
    When I call the discover tool with no session data
    Then the result is valid JSON
    And the result contains "No experiment data available"

  Scenario: MCP provenance tool returns informative message for unknown finding
    Given the MCP server is created
    When I call the provenance tool with finding_id "unknown-abc"
    Then the result is valid JSON
    And the result contains "No provenance chain registered"

  # -----------------------------------------------------------------------
  # CLI reproduce — C5 REPRODUCE
  # -----------------------------------------------------------------------

  Scenario: reproduce command confirms identical output for same seed
    Given a data directory with CSV files for reproduce
    When I run "labclaw reproduce" with seed 42
    Then the output is valid JSON
    And "reproducible" is true in the result
    And "diff" is null in the result

  Scenario: reproduce command includes findings in comparison (C5 REPRODUCE)
    Given a data directory with CSV files for reproduce
    When I run "labclaw reproduce" with seed 42
    Then the output contains run1 and run2 findings

  Scenario: reproduce --help prints usage
    When I run "labclaw reproduce --help"
    Then the reproduce output contains "data-dir"

  Scenario: reproduce command with no args exits with error
    When I run "labclaw reproduce" with no arguments
    Then the reproduce command exits with an error
