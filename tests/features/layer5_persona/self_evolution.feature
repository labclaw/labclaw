Feature: Self-Evolution (L5)
  The system improves its own analytical strategies through a
  rigorous 7-step evolution cycle with regression prevention.

  Background:
    Given the evolution engine is initialized

  Scenario: Measure fitness for a target
    When I measure fitness for target "analysis_params" with metrics:
      | metric     | value |
      | accuracy   | 0.85  |
      | efficiency | 0.72  |
    Then a FitnessScore is returned with 2 metrics
    And an event "evolution.fitness.measured" is emitted

  Scenario: Propose evolution candidates
    When I propose 3 candidates for target "analysis_params"
    Then 3 EvolutionCandidates are returned
    And each candidate has a description and config_diff

  Scenario: Run a complete evolution cycle through promotion
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    When I start an evolution cycle
    Then the cycle is in stage "backtest"
    And an event "evolution.cycle.started" is emitted
    When I advance with fitness accuracy 0.85
    Then the cycle is in stage "shadow"
    When I advance with fitness accuracy 0.87
    Then the cycle is in stage "canary"
    When I advance with fitness accuracy 0.88
    Then the cycle is in stage "promoted" and promoted is true
    And an event "evolution.cycle.promoted" is emitted

  Scenario: Auto-rollback on fitness regression
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    And a started evolution cycle in stage "backtest"
    When I advance with fitness accuracy 0.60
    Then the cycle is rolled back
    And the stage is "rolled_back"
    And an event "evolution.cycle.rolled_back" is emitted

  Scenario: Get evolution history
    Given 2 completed evolution cycles for "analysis_params"
    When I get history for target "analysis_params"
    Then I receive 2 cycles
