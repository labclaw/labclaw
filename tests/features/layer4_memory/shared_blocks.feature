Feature: Shared Blocks (Tier C)
  SQLite-backed key-value store for agent working memory.

  @wip
  Scenario: Shared blocks backend can be instantiated
    Given the shared blocks backend is implemented
    Then accessing shared blocks succeeds
