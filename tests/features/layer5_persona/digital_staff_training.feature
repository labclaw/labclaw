Feature: Digital Staff Training
  Digital members are trained through benchmarks and can earn
  promotions through demonstrated competence.

  Background:
    Given the persona manager is initialized

  Scenario: Create a digital intern
    When I create a digital member "alpha" with role "digital_intern"
    Then member "alpha" exists with role "digital_intern"
    And member "alpha" is digital
    And an event "persona.member.created" is emitted

  Scenario: Create a digital analyst
    When I create a digital member "beta" with role "digital_analyst"
    Then member "beta" exists with role "digital_analyst"
    And member "beta" is digital
    And an event "persona.member.created" is emitted

  Scenario: Create a digital specialist
    When I create a digital member "gamma" with role "digital_specialist"
    Then member "gamma" exists with role "digital_specialist"
    And member "gamma" is digital
    And an event "persona.member.created" is emitted

  Scenario: Create a human member
    When I create a human member "dr_jones" with role "postdoc"
    Then member "dr_jones" exists with role "postdoc"
    And member "dr_jones" is not digital
    And an event "persona.member.created" is emitted

  Scenario: Create a human PI member
    When I create a human member "prof_chen" with role "pi"
    Then member "prof_chen" exists with role "pi"
    And member "prof_chen" is not digital

  Scenario: Record benchmark results
    Given digital member "alpha" with role "digital_intern" exists
    When I record a benchmark for "alpha" with task "analysis" and score 0.85
    Then "alpha" has 1 benchmark recorded
    And an event "persona.benchmark.recorded" is emitted

  Scenario: Record multiple benchmarks for different tasks
    Given digital member "alpha" with role "digital_intern" exists
    When I record a benchmark for "alpha" with task "analysis" and score 0.85
    And I record a benchmark for "alpha" with task "protocol" and score 0.70
    And I record a benchmark for "alpha" with task "reporting" and score 0.90
    Then "alpha" has 3 benchmarks recorded

  Scenario: Benchmark score at lower boundary (0.0) is valid
    Given digital member "alpha" with role "digital_intern" exists
    When I record a benchmark for "alpha" with task "analysis" and score 0.0
    Then "alpha" has 1 benchmark recorded

  Scenario: Benchmark score at upper boundary (1.0) is valid
    Given digital member "alpha" with role "digital_intern" exists
    When I record a benchmark for "alpha" with task "analysis" and score 1.0
    Then "alpha" has 1 benchmark recorded

  Scenario: Benchmark score above 1.0 is invalid
    Given digital member "alpha" with role "digital_intern" exists
    When I try to record an invalid benchmark for "alpha" with score 1.5
    Then a validation error is raised for the benchmark

  Scenario: Benchmark score below 0.0 is invalid
    Given digital member "alpha" with role "digital_intern" exists
    When I try to record an invalid benchmark for "alpha" with score -0.1
    Then a validation error is raised for the benchmark

  Scenario: Get all benchmarks for a member
    Given digital member "alpha" with role "digital_intern" exists
    And "alpha" has 5 benchmarks with average score 0.80
    When I get all benchmarks for "alpha"
    Then 5 benchmarks are returned for "alpha"

  Scenario: Record a correction
    Given digital member "alpha" with role "digital_intern" exists
    When I record a correction for "alpha" with category "analysis_error" and detail "Wrong baseline used"
    Then "alpha" has 1 correction recorded
    And an event "persona.correction.recorded" is emitted

  Scenario: Record a protocol violation correction
    Given digital member "alpha" with role "digital_intern" exists
    When I record a correction for "alpha" with category "protocol_violation" and detail "Skipped calibration step"
    Then "alpha" has 1 correction recorded
    And an event "persona.correction.recorded" is emitted

  Scenario: Record a safety incident correction
    Given digital member "alpha" with role "digital_intern" exists
    When I record a correction for "alpha" with category "safety_incident" and detail "Exceeded temperature limit"
    Then "alpha" has 1 correction recorded
    And an event "persona.correction.recorded" is emitted

  Scenario: Record multiple corrections of different categories
    Given digital member "alpha" with role "digital_intern" exists
    When I record a correction for "alpha" with category "analysis_error" and detail "Wrong baseline used"
    And I record a correction for "alpha" with category "protocol_violation" and detail "Skipped step"
    Then "alpha" has 2 corrections recorded

  Scenario: Get all corrections for a member
    Given digital member "alpha" with role "digital_intern" exists
    When I record a correction for "alpha" with category "analysis_error" and detail "Wrong baseline used"
    And I record a correction for "alpha" with category "protocol_violation" and detail "Skipped step"
    When I get all corrections for "alpha"
    Then 2 corrections are returned for "alpha"

  Scenario: Member training history includes benchmarks and corrections
    Given digital member "alpha" with role "digital_intern" exists
    And "alpha" has 3 benchmarks with average score 0.80
    When I record a correction for "alpha" with category "analysis_error" and detail "Wrong baseline"
    Then "alpha" has 3 benchmarks recorded
    And "alpha" has 1 correction recorded

  Scenario: Get benchmarks for nonexistent member raises KeyError
    When I try to get benchmarks for member id "bad-id-xyz"
    Then a KeyError is raised for member lookup

  Scenario: Get corrections for nonexistent member raises KeyError
    When I try to get corrections for member id "bad-id-xyz"
    Then a KeyError is raised for member lookup

  Scenario: Record benchmark for nonexistent member raises KeyError
    When I try to record a benchmark for nonexistent member "bad-id-abc"
    Then a KeyError is raised for member lookup

  Scenario: Record correction for nonexistent member raises KeyError
    When I try to record a correction for nonexistent member "bad-id-abc"
    Then a KeyError is raised for member lookup

  Scenario: Correction entry stores corrected_by field
    Given digital member "alpha" with role "digital_intern" exists
    When I record a correction for "alpha" with category "analysis_error" corrected by "supervisor_1"
    Then the correction has corrected_by "supervisor_1"
