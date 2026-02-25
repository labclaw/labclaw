Feature: Self-Evolution Cycles (C2: EVOLVE)
  The system improves through iterative evolution cycles,
  tracking fitness across runs and demonstrating that adaptation
  outperforms a no-evolution baseline.

  Background:
    Given an evolution runner is available

  Scenario: Evolution runner completes 10 cycles
    Given an evolution runner configured for 10 cycles
    When I run evolution on behavioral data
    Then 10 cycles are completed
    And fitness scores are recorded for each cycle

  Scenario: Evolution improves fitness over time
    Given an evolution runner configured for 10 cycles
    When I run evolution on behavioral data
    Then the final fitness is higher than the initial fitness

  Scenario: Ablation shows evolution contributes
    Given an evolution runner configured for 5 cycles
    When I run full evolution and no-evolution ablation
    Then the full condition has higher mean fitness

  Scenario: Evolution is deterministic with seed
    Given an evolution runner with seed 42
    When I run evolution twice on the same data
    Then both runs produce identical fitness trajectories

  Scenario: Evolution result contains required fields
    Given an evolution runner configured for 3 cycles
    When I run evolution on behavioral data
    Then the result has a condition field set to "full"
    And the result has a non-empty fitness_scores list
    And the result has a positive mean_fitness

  Scenario: Ablation result has correct condition label
    Given an evolution runner configured for 3 cycles
    When I run the no-evolution ablation
    Then the ablation result condition is "no_evolution"

  Scenario: Fitness improvement meets C2 threshold
    Given an evolution runner configured for 10 cycles
    When I run evolution on behavioral data
    Then the improvement percentage is at least 15 percent

  Scenario: Evolution runner records fitness in engine tracker
    Given an evolution runner configured for 4 cycles with shared engine
    When I run evolution with the shared engine
    Then the engine tracker has 4 fitness entries for analysis_params
