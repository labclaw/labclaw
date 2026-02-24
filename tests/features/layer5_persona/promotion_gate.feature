Feature: Promotion Gates
  Digital staff earn promotions by meeting benchmark thresholds.

  Background:
    Given the persona manager is initialized

  Scenario: Intern eligible for promotion after meeting benchmarks
    Given digital member "alpha" with role "digital_intern" exists
    And "alpha" has 10 benchmarks with average score 0.75
    When I check promotion eligibility for "alpha"
    Then "alpha" is eligible for promotion to "digital_analyst"

  Scenario: Intern not eligible with insufficient benchmarks
    Given digital member "alpha" with role "digital_intern" exists
    And "alpha" has 5 benchmarks with average score 0.80
    When I check promotion eligibility for "alpha"
    Then "alpha" is not eligible for promotion

  Scenario: Promote a digital intern to analyst
    Given digital member "alpha" with role "digital_intern" exists
    And "alpha" has 10 benchmarks with average score 0.75
    When I promote "alpha"
    Then "alpha" has role "digital_analyst"
    And an event "persona.member.promoted" is emitted

  Scenario: Demote a digital analyst
    Given digital member "beta" with role "digital_analyst" exists
    When I demote "beta"
    Then "beta" has role "digital_intern"
    And an event "persona.member.demoted" is emitted
