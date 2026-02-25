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

  Scenario: Analyst eligible for promotion to specialist
    Given digital member "gamma" with role "digital_analyst" exists
    And "gamma" has 25 benchmarks with average score 0.90
    When I check promotion eligibility for "gamma"
    Then "gamma" is eligible for promotion to "digital_specialist"

  Scenario: Analyst not eligible with insufficient average score
    Given digital member "gamma" with role "digital_analyst" exists
    And "gamma" has 25 benchmarks with average score 0.80
    When I check promotion eligibility for "gamma"
    Then "gamma" is not eligible for promotion

  Scenario: Specialist cannot be promoted further
    Given digital member "delta" with role "digital_specialist" exists
    And "delta" has 50 benchmarks with average score 0.95
    When I check promotion eligibility for "delta"
    Then "delta" is not eligible for promotion

  Scenario: Member with zero benchmarks is not eligible
    Given digital member "epsilon" with role "digital_intern" exists
    When I check promotion eligibility for "epsilon"
    Then "epsilon" is not eligible for promotion

  Scenario: Promotion threshold boundary — exactly at minimum score
    Given digital member "zeta" with role "digital_intern" exists
    And "zeta" has 10 benchmarks with average score 0.70
    When I check promotion eligibility for "zeta"
    Then "zeta" is eligible for promotion to "digital_analyst"

  Scenario: Promotion threshold boundary — just below minimum score
    Given digital member "theta" with role "digital_intern" exists
    And "theta" has 10 benchmarks with average score 0.69
    When I check promotion eligibility for "theta"
    Then "theta" is not eligible for promotion

  Scenario: Promote analyst to specialist
    Given digital member "iota" with role "digital_analyst" exists
    And "iota" has 25 benchmarks with average score 0.90
    When I promote "iota"
    Then "iota" has role "digital_specialist"
    And an event "persona.member.promoted" is emitted

  Scenario: Demote specialist to analyst
    Given digital member "kappa" with role "digital_specialist" exists
    When I demote "kappa"
    Then "kappa" has role "digital_analyst"
    And an event "persona.member.demoted" is emitted

  Scenario: Cannot demote member already at minimum digital role
    Given digital member "lambda" with role "digital_intern" exists
    When I try to demote "lambda"
    Then a ValueError is raised for demotion

  Scenario: Cannot promote a human member
    Given human member "dr_smith" with role "postdoc" exists
    When I try to promote "dr_smith"
    Then a ValueError is raised for promotion

  Scenario: Cannot demote a human member
    Given human member "dr_smith" with role "postdoc" exists
    When I try to demote "dr_smith"
    Then a ValueError is raised for demotion

  Scenario: Get nonexistent member raises KeyError
    When I try to get member with id "nonexistent-id-12345"
    Then a KeyError is raised

  Scenario: Corrections do not prevent promotion if benchmark threshold is met
    Given digital member "mu" with role "digital_intern" exists
    And "mu" has 10 benchmarks with average score 0.75
    And "mu" has a correction with category "analysis_error"
    When I check promotion eligibility for "mu"
    Then "mu" is eligible for promotion to "digital_analyst"

  Scenario: Promoted member has promoted_at timestamp set
    Given digital member "nu" with role "digital_intern" exists
    And "nu" has 10 benchmarks with average score 0.75
    When I promote "nu"
    Then "nu" has a promoted_at timestamp

  Scenario: Promoted member role is updated in the manager
    Given digital member "xi" with role "digital_intern" exists
    And "xi" has 10 benchmarks with average score 0.75
    When I promote "xi"
    And I check promotion eligibility for "xi"
    Then "xi" is not eligible for promotion
