Feature: Discovery Loop (ASK -> HYPOTHESIZE)
  The system mines patterns from experimental data and generates
  testable hypotheses.

  Background:
    Given the pattern miner is initialized

  Scenario: Find correlations in numeric data
    Given experimental data with columns "speed", "accuracy", "temperature"
    And 20 rows where speed and accuracy are strongly correlated
    When I find correlations with threshold 0.5
    Then at least 1 correlation pattern is found
    And the pattern describes "speed" and "accuracy"
    And an event "discovery.pattern.found" is emitted

  Scenario: Detect anomalies in session data
    Given experimental data with 20 normal rows and 2 anomalous rows for column "latency"
    When I find anomalies with z-threshold 2.0
    Then at least 1 anomaly pattern is found
    And the anomaly references the outlier rows

  Scenario: Run full mining pipeline
    Given experimental data with correlations and anomalies
    When I run the full mining pipeline
    Then a MiningResult is returned with patterns
    And an event "discovery.mining.completed" is emitted

  Scenario: Generate hypotheses from patterns
    Given the hypothesis generator is initialized
    And 2 correlation patterns exist
    When I generate hypotheses
    Then at least 2 hypotheses are generated
    And each hypothesis has a statement
    And each hypothesis is marked as testable
    And an event "discovery.hypothesis.created" is emitted

  Scenario: Mining on insufficient data returns empty
    Given experimental data with only 3 rows
    When I run the full mining pipeline with min_sessions 10
    Then the MiningResult has 0 patterns

  Scenario: Temporal trend detection - increasing
    Given experimental data with an increasing temporal trend for column "score"
    When I find temporal patterns
    Then at least 1 temporal pattern is found
    And the temporal pattern direction is "increasing"

  Scenario: Temporal trend detection - decreasing
    Given experimental data with a decreasing temporal trend for column "response_time"
    When I find temporal patterns
    Then at least 1 temporal pattern is found
    And the temporal pattern direction is "decreasing"

  Scenario: No temporal column yields empty temporal patterns
    Given experimental data with no timestamp column and 20 rows
    When I find temporal patterns
    Then 0 temporal patterns are found

  Scenario: All identical values produce no correlations due to zero std
    Given experimental data with 20 rows where all values are identical
    When I find correlations with threshold 0.5
    Then 0 correlation patterns are found

  Scenario: Weak correlations below threshold are filtered out
    Given experimental data with 20 rows of weakly correlated columns
    When I find correlations with threshold 0.8
    Then 0 correlation patterns are found

  Scenario: Mining with custom feature_columns config
    Given experimental data with mixed columns including non-numeric
    When I run the full mining pipeline with feature_columns "x" and "y"
    Then the MiningResult only includes patterns for specified columns

  Scenario: Mining with non-numeric columns ignores them
    Given experimental data with 15 rows containing string columns
    When I run the full mining pipeline
    Then the MiningResult does not include string column patterns

  Scenario: All identical values produce no anomalies
    Given experimental data with 20 identical single-column values in column "weight"
    When I find anomalies with z-threshold 2.0
    Then 0 anomaly patterns are found

  Scenario: Correlations with missing values in some rows
    Given experimental data with 20 rows where some rows have missing values
    When I find correlations with threshold 0.5
    Then the miner runs without error

  Scenario: Generate hypothesis from anomaly pattern
    Given the hypothesis generator is initialized
    And 1 anomaly pattern exists
    When I generate hypotheses
    Then at least 1 hypothesis is generated
    And the hypothesis mentions "external factor"

  Scenario: Generate hypothesis from temporal pattern
    Given the hypothesis generator is initialized
    And 1 temporal pattern exists
    When I generate hypotheses
    Then at least 1 hypothesis is generated
    And the hypothesis mentions "Trend"

  Scenario: Generate hypothesis from cluster pattern
    Given the hypothesis generator is initialized
    And 1 cluster pattern exists
    When I generate hypotheses
    Then at least 1 hypothesis is generated
    And the hypothesis mentions "clusters"

  Scenario: Unknown pattern type returns no hypothesis
    Given the hypothesis generator is initialized
    And 1 unknown pattern type exists
    When I generate hypotheses
    Then 0 hypotheses are generated
