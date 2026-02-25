Feature: Experiment Conductor (EXPERIMENT)
  The system proposes experimental parameters via Bayesian optimization,
  validates safety, and gates on human approval.

  Background:
    Given a parameter space with dimensions:
      | name        | low | high |
      | temperature | 20  | 40   |
      | duration    | 10  | 120  |
    And the optimizer is initialized with this space

  Scenario: Suggest experimental parameters
    When I request 3 experiment proposals
    Then 3 proposals are returned
    And each proposal has parameters within bounds
    And an event "optimization.proposal.created" is emitted

  Scenario: Record optimization result and track best
    Given I have suggested and recorded 5 experiments with objective values
    When I query the best result
    Then the best result has the highest objective value

  Scenario: Scientific safety validates parameter bounds
    Given safety constraints:
      | parameter   | min_value | max_value |
      | temperature | 22        | 37        |
      | duration    | 15        | 90        |
    When I validate a proposal with temperature 25 and duration 60
    Then the scientific safety check passes

  Scenario: Scientific safety blocks out-of-range parameters
    Given safety constraints:
      | parameter   | min_value | max_value |
      | temperature | 22        | 37        |
    When I validate a proposal with temperature 45
    Then the scientific safety check fails
    And the safety level is "blocked"

  Scenario: Approval workflow - approve
    Given a proposal that passed scientific safety
    When I request approval
    Then an approval request is created with status "pending"
    When the PI approves the request
    Then the approval status is "approved"
    And an event "optimization.approval.decided" is emitted

  Scenario: Approval workflow - reject
    Given a proposal that passed scientific safety
    When I request approval
    And the PI rejects the request with reason "Too risky"
    Then the approval status is "rejected"

  Scenario: Optimizer with 1 dimension only
    Given a parameter space with 1 dimension "voltage" from 1.0 to 5.0
    When I request 2 proposals from single dimension optimizer
    Then 2 proposals are returned from single dimension optimizer
    And each proposal has a "voltage" parameter within 1.0 to 5.0

  Scenario: Record result updates history
    Given I record an experiment result with objective value 0.75
    When I query the optimizer history
    Then the history has 1 result
    And the recorded objective value is 0.75

  Scenario: Safety check with multiple constraints - all pass
    Given safety constraints:
      | parameter   | min_value | max_value |
      | temperature | 20        | 40        |
      | duration    | 10        | 120       |
    When I validate a proposal with temperature 30 and duration 60
    Then the scientific safety check passes
    And all safety check details passed

  Scenario: Safety check with multiple constraints - one fails
    Given safety constraints:
      | parameter   | min_value | max_value |
      | temperature | 20        | 35        |
      | duration    | 10        | 120       |
    When I validate a proposal with temperature 40 and duration 60
    Then the scientific safety check fails
    And at least one safety check detail failed

  Scenario: Approval blocked when safety check failed
    Given a proposal that failed scientific safety
    When I attempt to request approval for failed proposal
    Then a ValueError is raised for failed approval

  Scenario: Full pipeline suggest validate approve
    Given the experiment pipeline is initialized with safe constraints
    When I run the full proposal pipeline
    Then an approval request with status "pending" is produced by pipeline

  Scenario: Multiple proposals in sequence increment iteration counter
    When I request 1 experiment proposals
    And I request 1 experiment proposals
    Then the second proposal has a higher iteration number
