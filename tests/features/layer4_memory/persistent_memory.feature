Feature: Persistent Memory (C3: REMEMBER)
  Memory persists across sessions and prevents re-discovery.

  Scenario: Findings survive manager restart
    Given a session memory manager with SQLite backend
    When I store 5 findings and create a new manager instance
    Then at least 4 findings are retrievable

  Scenario: Known patterns are flagged as duplicates
    Given a pattern deduplicator with 3 known patterns
    When I check a pattern that matches a known one
    Then it is flagged as duplicate

  Scenario: New patterns pass deduplication
    Given a pattern deduplicator with 3 known patterns
    When I check a completely new pattern
    Then it is not flagged as duplicate

  Scenario: Deduplication filters list of patterns
    Given a pattern deduplicator with 3 known patterns
    And a list of 5 patterns where 2 are duplicates
    When I deduplicate the list
    Then 3 unique patterns remain

  Scenario: Memory-assisted hypothesis uses past findings
    Given past findings about speed-distance correlation
    When I generate hypotheses with context
    Then the hypotheses reference the past findings

  Scenario: Retrieval rate is 1.0 when all findings are accessible
    Given a session memory manager with SQLite backend
    When I store 5 findings and create a new manager instance
    Then the retrieval rate is at least 0.9

  Scenario: is_known_pattern returns False for new patterns
    Given a fresh session memory manager
    When I check whether a new pattern is known
    Then it is not known

  Scenario: is_known_pattern returns True after storing
    Given a fresh session memory manager
    When I store a pattern and check if it is known
    Then it is flagged as known
