Feature: Statistical Validation (CONCLUDE)
  The system performs rigorous statistical validation of findings
  with full provenance tracking.

  Background:
    Given the statistical validator is initialized
    And the provenance tracker is initialized

  Scenario: Run a t-test on two groups
    Given group A has values [10.1, 10.5, 9.8, 10.3, 10.0]
    And group B has values [12.1, 12.5, 11.8, 12.3, 12.0]
    When I run a "t_test" on both groups
    Then the test result has a p-value less than 0.05
    And the test is significant
    And the effect size is calculated

  Scenario: Bonferroni correction adjusts p-values
    Given I have 3 test results with p-values [0.01, 0.03, 0.04]
    When I apply "bonferroni" correction
    Then the corrected p-values are [0.03, 0.09, 0.12]
    And only 1 result remains significant at alpha 0.05

  Scenario: Build a provenance chain for a finding
    When I build a provenance chain for finding "finding-001" with steps:
      | node_type | description |
      | subject   | Mouse #42 genotype Thy1-GCaMP6 |
      | session   | Recording session 2026-01-15 |
      | recording | Two-photon calcium imaging |
      | analysis  | Suite2p ROI extraction |
      | finding   | Novel neural ensemble pattern |
    Then the chain has 5 steps
    And the chain is verified as valid
    And an event "validation.provenance.built" is emitted

  Scenario: Generate a validation report
    Given a completed t-test result
    And a provenance chain for finding "finding-002"
    When I generate a validation report
    Then the report contains the test results
    And the report contains the provenance chain
    And the report has a conclusion status
    And an event "validation.report.generated" is emitted

  Scenario: Insufficient sample size warns
    Given group A has values [1.0, 2.0]
    And group B has values [3.0, 4.0]
    When I run a "t_test" on both groups with min_sample_size 5
    Then the result includes a sample size warning
