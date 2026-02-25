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

  Scenario: Mann-Whitney test on ranked data
    Given group A has values [1.0, 2.0, 3.0, 4.0, 5.0]
    And group B has values [6.0, 7.0, 8.0, 9.0, 10.0]
    When I run a "mann_whitney" on both groups
    Then the test result has a p-value less than 0.05
    And the test is significant

  Scenario: Mann-Whitney test on overlapping groups is non-significant
    Given group A has values [5.0, 5.1, 4.9, 5.0, 5.0]
    And group B has values [5.0, 5.1, 4.9, 5.0, 5.0]
    When I run a "mann_whitney" on both groups
    Then the test is not significant

  Scenario: Permutation test with known different groups
    Given group A has values [1.0, 1.0, 1.0, 1.0, 1.0]
    And group B has values [10.0, 10.0, 10.0, 10.0, 10.0]
    When I run a "permutation" on both groups
    Then the test is significant

  Scenario: Permutation test with identical groups yields p near 1.0
    Given group A has values [5.0, 5.0, 5.0, 5.0, 5.0]
    And group B has values [5.0, 5.0, 5.0, 5.0, 5.0]
    When I run a "permutation" on both groups
    Then the permutation p-value is close to 1.0

  Scenario: Unknown test name raises ValueError
    Given group A has values [1.0, 2.0, 3.0]
    And group B has values [4.0, 5.0, 6.0]
    When I run an unknown test "fake_test"
    Then a ValueError is raised for unknown test

  Scenario: Empty group raises ValueError
    Given group A is empty
    And group B has values [1.0, 2.0, 3.0]
    When I run a t-test with empty group
    Then a ValueError is raised for empty group

  Scenario: Bonferroni with single test no adjustment
    Given I have 1 test results with p-values [0.02]
    When I apply "bonferroni" correction
    Then the corrected p-values are [0.02]
    And only 1 result remains significant at alpha 0.05

  Scenario: Validate finding with multiple tests
    Given group A has values [10.0, 11.0, 12.0, 10.5, 11.5]
    And group B has values [14.0, 15.0, 16.0, 14.5, 15.5]
    When I validate a finding with t_test and permutation tests
    Then the validation report has 2 tests
    And the report conclusion is not empty

  Scenario: Provenance chain with empty steps raises ValueError
    When I try to build a chain with empty steps
    Then a ValueError is raised for empty steps

  Scenario: Provenance chain verify fails on empty finding_id
    When I build a chain with empty finding_id
    Then the chain verification returns false

  Scenario: Provenance chain verify fails on empty node_id
    When I build a chain with a step missing node_id
    Then the chain verification returns false

  Scenario: Provenance chain verify fails on empty node_type
    When I build a chain with a step missing node_type
    Then the chain verification returns false

  Scenario: Provenance to_dict and from_dict round-trip
    Given a provenance chain for finding "finding-rt-001"
    When I serialize and deserialize the chain
    Then the round-tripped chain matches the original

  Scenario: Report to_markdown contains key sections
    Given a completed t-test result
    And a provenance chain for finding "finding-md-001"
    When I generate a validation report
    And I convert the report to markdown
    Then the markdown contains "## Summary"
    And the markdown contains "## Statistical Tests"
    And the markdown contains "## Provenance"
    And the markdown contains "## Conclusion"

  Scenario: Cohen's d with zero standard deviation returns 0.0
    When I compute cohens d with identical groups
    Then cohens d is 0.0

  Scenario: Cross-validation holdout basic case
    When I run holdout validation on 20 data points
    Then the holdout result has train_mean and test_mean and mae

  Scenario: Cross-validation kfold with k=5
    When I run kfold validation on 20 data points with k=5
    Then the kfold result has 5 fold_maes
    And the mean_mae is non-negative

  Scenario: Cross-validation permutation test with identical groups yields high p
    When I run cv permutation test with identical groups
    Then the cv permutation p-value is at least 0.5
