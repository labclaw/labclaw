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
