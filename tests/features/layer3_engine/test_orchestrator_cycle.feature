Feature: Orchestration Cycle (7-step scientific method)
  The orchestrator runs a complete scientific method cycle:
  OBSERVE -> ASK -> HYPOTHESIZE -> PREDICT -> EXPERIMENT -> ANALYZE -> CONCLUDE

  Scenario: Complete scientific cycle on valid experiment data
    Given 20 rows of experiment data with numeric columns
    When the orchestrator runs a complete cycle
    Then all 7 steps should execute
    And patterns should be discovered
    And hypotheses should be generated

  Scenario: Orchestrator skips steps when data is insufficient
    Given 5 rows of experiment data
    When the orchestrator runs a complete cycle
    Then the ask step should be skipped
    And the reason should mention too few rows

  Scenario: Orchestrator handles individual step failure gracefully
    Given a step that will fail during execution
    When the orchestrator runs a complete cycle
    Then the cycle should complete with success=False
    And the failing step should be recorded
