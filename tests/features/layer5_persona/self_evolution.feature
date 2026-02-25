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

  Scenario: Measure fitness with a single metric
    When I measure fitness for target "prompts" with metrics:
      | metric   | value |
      | latency  | 0.90  |
    Then a FitnessScore is returned with 1 metrics
    And an event "evolution.fitness.measured" is emitted

  Scenario: Fitness tracker returns latest score
    Given a baseline fitness for "routing" with accuracy 0.70
    When I measure fitness for target "routing" with metrics:
      | metric   | value |
      | accuracy | 0.78  |
    Then the latest fitness for "routing" has accuracy 0.78

  Scenario: Fitness tracker returns full history for target
    Given a baseline fitness for "heuristics" with accuracy 0.65
    And a baseline fitness for "heuristics" with accuracy 0.70
    When I get fitness history for "heuristics"
    Then the fitness history has 2 entries

  Scenario: Stage transition backtest to shadow
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    When I start an evolution cycle
    And I advance with fitness accuracy 0.85
    Then the cycle is in stage "shadow"
    And an event "evolution.cycle.advanced" is emitted

  Scenario: Stage transition shadow to canary
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    When I start an evolution cycle
    And I advance with fitness accuracy 0.85
    And I advance with fitness accuracy 0.87
    Then the cycle is in stage "canary"

  Scenario: Rollback from shadow stage
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    When I start an evolution cycle
    And I advance with fitness accuracy 0.85
    And I advance with fitness accuracy 0.60
    Then the cycle is rolled back
    And the stage is "rolled_back"
    And an event "evolution.cycle.rolled_back" is emitted

  Scenario: Rollback from canary stage
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    When I start an evolution cycle
    And I advance with fitness accuracy 0.85
    And I advance with fitness accuracy 0.87
    And I advance with fitness accuracy 0.55
    Then the cycle is rolled back
    And the stage is "rolled_back"

  Scenario: Manual rollback of a cycle
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    And a started evolution cycle in stage "backtest"
    When I manually rollback the cycle with reason "configuration incompatible"
    Then the cycle is rolled back
    And the rollback reason is "configuration incompatible"
    And an event "evolution.cycle.rolled_back" is emitted

  Scenario: Cannot advance an already-promoted cycle
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    And a promoted evolution cycle
    When I try to advance the promoted cycle
    Then a ValueError is raised

  Scenario: Cannot advance an already-rolled-back cycle
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    And a rolled-back evolution cycle
    When I try to advance the rolled-back cycle
    Then a ValueError is raised

  Scenario: Propose candidates for prompts target
    When I propose 2 candidates for target "prompts"
    Then 2 EvolutionCandidates are returned
    And each candidate has a description and config_diff

  Scenario: Propose candidates for routing target
    When I propose 2 candidates for target "routing"
    Then 2 EvolutionCandidates are returned

  Scenario: Propose candidates for heuristics target
    When I propose 2 candidates for target "heuristics"
    Then 2 EvolutionCandidates are returned

  Scenario: Propose candidates for strategy target
    When I propose 2 candidates for target "strategy"
    Then 2 EvolutionCandidates are returned

  Scenario: Evolution history ordered by time
    Given 3 completed evolution cycles for "analysis_params"
    When I get history for target "analysis_params"
    Then I receive 3 cycles
    And the history is ordered by start time

  Scenario: Get history filtered by target returns only matching cycles
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    And a started evolution cycle in stage "backtest"
    And a baseline fitness for "prompts" with accuracy 0.75
    And a candidate for "prompts"
    And a started prompts evolution cycle
    When I get history for target "analysis_params"
    Then I receive 1 cycles

  Scenario: Fitness comparison shows improvement
    Given a baseline fitness for "analysis_params" with accuracy 0.70
    When I measure fitness for target "analysis_params" with metrics:
      | metric   | value |
      | accuracy | 0.85  |
    Then the new fitness is better than baseline

  Scenario: Boundary condition — fitness just above rollback threshold does not rollback
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    And a started evolution cycle in stage "backtest"
    When I advance with fitness accuracy 0.73
    Then the cycle is in stage "shadow"

  Scenario: Get cycle by ID
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    When I start an evolution cycle
    Then I can retrieve the cycle by its ID

  Scenario: Get active cycles returns only non-terminal cycles
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a candidate for "analysis_params"
    And a started evolution cycle in stage "backtest"
    When I get active cycles
    Then 1 active cycle is returned

  Scenario: Multiple targets can evolve independently
    Given a baseline fitness for "analysis_params" with accuracy 0.80
    And a baseline fitness for "prompts" with accuracy 0.75
    When I measure fitness for target "analysis_params" with metrics:
      | metric   | value |
      | accuracy | 0.82  |
    And I measure fitness for target "prompts" with metrics:
      | metric   | value |
      | accuracy | 0.78  |
    Then the latest fitness for "analysis_params" has accuracy 0.82
    And the latest fitness for "prompts" has accuracy 0.78
