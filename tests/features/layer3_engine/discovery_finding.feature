Feature: First Discovery (C1: DISCOVER)
  The pipeline discovers statistically significant patterns in data.

  Scenario: Pipeline discovers correlated variables
    Given behavioral data with embedded speed-distance correlation
    When I run a full discovery cycle
    Then at least 1 pattern is found
    And the pattern has a correlation coefficient above 0.3

  Scenario: LLM hypothesis generator respects cost guard
    Given a hypothesis generator with max_calls=2
    When I generate hypotheses 5 times
    Then only 2 LLM calls are made
    And the remaining use template fallback

  Scenario: Discovery writes p-values to memory
    Given behavioral data with real statistical patterns
    And a temporary memory directory
    When I run a full discovery cycle with memory
    Then the memory file contains statistical results
