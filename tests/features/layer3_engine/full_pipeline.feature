Feature: Full Scientific Pipeline (end-to-end)
  The ScientificLoop runs all 7 steps on real-format behavioral data.

  Scenario: Pipeline produces patterns from behavioral data
    Given behavioral data from 2 sessions with 50 rows each
    When I run a full scientific method cycle
    Then the cycle completes successfully
    And at least 1 pattern is found

  Scenario: Pipeline is deterministic with same input
    Given behavioral data from 2 sessions with 50 rows each
    When I run 2 scientific method cycles on the same data
    Then both cycles find the same number of patterns

  Scenario: Pipeline writes memory after conclusion
    Given behavioral data from 2 sessions with 50 rows each
    And a temporary memory directory
    When I run a full scientific method cycle with memory writing
    Then a MEMORY.md file is created in the memory directory
