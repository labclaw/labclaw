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

  Scenario: Record benchmark results
    Given digital member "alpha" with role "digital_intern" exists
    When I record a benchmark for "alpha" with task "analysis" and score 0.85
    Then "alpha" has 1 benchmark recorded
    And an event "persona.benchmark.recorded" is emitted

  Scenario: Record a correction
    Given digital member "alpha" with role "digital_intern" exists
    When I record a correction for "alpha" with category "analysis_error" and detail "Wrong baseline used"
    Then "alpha" has 1 correction recorded
    And an event "persona.correction.recorded" is emitted
