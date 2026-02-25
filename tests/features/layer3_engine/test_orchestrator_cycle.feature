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

  Scenario: Cycle with empty data skips observe
    Given empty experiment data
    When the orchestrator runs a complete cycle
    Then the observe step should be skipped

  Scenario: Cycle produces CycleResult with a cycle_id
    Given 20 rows of experiment data with numeric columns
    When the orchestrator runs a complete cycle
    Then the cycle result has a non-empty cycle_id

  Scenario: Cycle with real mining data produces findings in conclude
    Given 20 rows of experiment data with numeric columns
    When the orchestrator runs a complete cycle
    Then the cycle result has at least 1 finding

  Scenario: Cycle emits orchestrator started and completed events
    Given 20 rows of experiment data with numeric columns
    When the orchestrator runs a complete cycle with event capture
    Then an event "orchestrator.cycle.started" is emitted
    And an event "orchestrator.cycle.completed" is emitted

  Scenario: Cycle duration is positive
    Given 20 rows of experiment data with numeric columns
    When the orchestrator runs a complete cycle
    Then the cycle total_duration is greater than 0.0

  Scenario: ASK step skipped when only 9 rows provided
    Given 9 rows of experiment data
    When the orchestrator runs a complete cycle
    Then the ask step should be skipped

  Scenario: Cycle with multiple failing steps marks success as False
    Given a step that will fail during execution
    When the orchestrator runs a complete cycle
    Then the cycle should complete with success=False
