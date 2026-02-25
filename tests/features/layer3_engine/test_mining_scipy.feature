Feature: Pattern Mining with Scipy/Numpy (ASK step — scipy backend)
  The pattern miner uses scipy.stats.pearsonr for correlations and
  numpy for z-score anomaly detection. All statistical outputs carry
  p-values and the full evidence dict; pure-Python fallbacks are gone.

  Background:
    Given the pattern miner is initialized

  # ---------------------------------------------------------------------------
  # Pearson correlation via scipy — verifies scipy path produces p-value
  # ---------------------------------------------------------------------------

  Scenario: Scipy pearsonr correlation includes p-value in evidence
    Given 20 rows where speed and accuracy are strongly correlated
    When I find correlations with threshold 0.5
    Then at least 1 correlation pattern is found
    And the correlation evidence includes a p_value field

  Scenario: Scipy pearsonr correlation result is reproducible
    Given 20 rows where speed and accuracy are strongly correlated
    When I find correlations with threshold 0.5
    And I find correlations again with threshold 0.5
    Then both runs return the same number of patterns

  Scenario: Scipy pearsonr correlation coefficient is within valid range
    Given 20 rows where speed and accuracy are strongly correlated
    When I find correlations with threshold 0.0
    Then every correlation pattern has r between -1.0 and 1.0

  # ---------------------------------------------------------------------------
  # Anomaly detection via numpy z-score
  # ---------------------------------------------------------------------------

  Scenario: Numpy z-score anomaly detection records mean and std in evidence
    Given experimental data with 20 normal rows and 2 anomalous rows for column "latency"
    When I find anomalies with z-threshold 2.0
    Then at least 1 anomaly pattern is found
    And the anomaly evidence includes mean and std fields

  Scenario: Anomaly confidence is clamped between 0 and 1
    Given experimental data with 20 normal rows and 2 anomalous rows for column "latency"
    When I find anomalies with z-threshold 2.0
    Then every anomaly pattern has confidence between 0.0 and 1.0

  # ---------------------------------------------------------------------------
  # Temporal trend detection
  # ---------------------------------------------------------------------------

  Scenario: Temporal pattern evidence contains direction and both half means
    Given experimental data with an increasing temporal trend for column "score"
    When I find temporal patterns
    Then at least 1 temporal pattern is found
    And the temporal evidence includes direction and half means

  # ---------------------------------------------------------------------------
  # MiningConfig validation
  # ---------------------------------------------------------------------------

  Scenario: MiningConfig defaults are sane
    When I create a default MiningConfig
    Then the default min_sessions is 10
    And the default correlation_threshold is 0.5
    And the default anomaly_z_threshold is 2.0
    And the default feature_columns is empty

  Scenario: MiningConfig with custom parameters is respected
    Given experimental data with only 3 rows
    When I run the full mining pipeline with min_sessions 5
    Then the MiningResult config min_sessions is 5

  # ---------------------------------------------------------------------------
  # Data summary in MiningResult
  # ---------------------------------------------------------------------------

  Scenario: MiningResult data_summary contains row_count and numeric_columns
    Given experimental data with correlations and anomalies
    When I run the full mining pipeline
    Then the data_summary contains row_count
    And the data_summary contains numeric_columns

  Scenario: MiningResult stores the last result on the miner
    Given experimental data with correlations and anomalies
    When I run the full mining pipeline
    Then the miner last_result is set

  # ---------------------------------------------------------------------------
  # Edge cases
  # ---------------------------------------------------------------------------

  Scenario: Empty data produces zero patterns and correct summary
    Given empty mining data
    When I run the full mining pipeline
    Then the MiningResult has 0 patterns
    And the data_summary row_count is 0

  Scenario: Data below min_sessions threshold produces zero patterns
    Given experimental data with only 3 rows
    When I run the full mining pipeline with min_sessions 10
    Then the MiningResult has 0 patterns

  Scenario: Single numeric column produces no correlations but may have anomalies
    Given experimental data with 15 rows and a single numeric column
    When I run the full mining pipeline
    Then no correlation patterns are in the result
