Feature: Shared Blocks (Tier C)
  SQLite-backed key-value store for agent working memory.
  Each block is a JSON-serializable dict with metadata.

  Background:
    Given the shared blocks backend is initialized in memory mode

  # -----------------------------------------------------------------------
  # Instantiation
  # -----------------------------------------------------------------------

  Scenario: Shared blocks backend can be instantiated
    Given the shared blocks backend is implemented
    Then accessing shared blocks succeeds

  Scenario: Empty backend has no keys
    When I list all block keys
    Then the block key list is empty

  # -----------------------------------------------------------------------
  # Set and get
  # -----------------------------------------------------------------------

  Scenario: Set and get a key-value pair
    When I set block "agent-state" to value "running"
    And I get block "agent-state"
    Then the block value contains "running"

  Scenario: Get nonexistent key returns None
    When I get block "does-not-exist"
    Then the block result is None

  Scenario: Overwrite existing key
    When I set block "counter" to value "first"
    And I set block "counter" to value "second"
    And I get block "counter"
    Then the block value contains "second"

  Scenario: Store complex value as dict
    When I set block "config" to complex value with key "model" and value "gemini-3-pro-preview"
    And I get block "config"
    Then the block complex value has key "model" equal to "gemini-3-pro-preview"

  # -----------------------------------------------------------------------
  # Delete
  # -----------------------------------------------------------------------

  Scenario: Delete an existing key
    When I set block "temp-key" to value "ephemeral"
    And I delete block "temp-key"
    And I get block "temp-key"
    Then the block result is None

  Scenario: Delete nonexistent key returns False
    When I delete block "nonexistent-key-xyz"
    Then the delete result is False

  Scenario: Delete existing key returns True
    When I set block "deletable-key" to value "exists"
    And I delete block "deletable-key"
    Then the delete result is True

  # -----------------------------------------------------------------------
  # List keys
  # -----------------------------------------------------------------------

  Scenario: List all keys after setting multiple blocks
    When I set block "block-a" to value "alpha"
    And I set block "block-b" to value "beta"
    And I set block "block-c" to value "gamma"
    And I list all block keys
    Then the block key list contains "block-a"
    And the block key list contains "block-b"
    And the block key list contains "block-c"

  # -----------------------------------------------------------------------
  # Exists check
  # -----------------------------------------------------------------------

  Scenario: Check if key exists after setting
    When I set block "exists-key" to value "yes"
    Then block "exists-key" exists in the backend

  Scenario: Check if nonexistent key does not exist
    Then block "never-set-key" does not exist in the backend
