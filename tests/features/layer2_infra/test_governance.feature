Feature: Governance
  Role-based permissions, safety rules, and audit logging
  protect the lab from unauthorized or dangerous actions.

  Scenario: PI role can perform any action
    Given a governance engine with default role permissions
    When the PI requests to "execute" an action
    Then the decision should be allowed

  Scenario: Undergraduate is denied execute permission
    Given a governance engine with default role permissions
    When an undergraduate requests to "execute" an action
    Then the decision should be denied
    And the reason should mention lacking permission

  Scenario: Safety rule blocks dangerous action
    Given a governance engine with a deny_if rule for "delete_all_data"
    When any user requests "delete_all_data"
    Then the decision should be denied
    And the audit log should record the denial

  Scenario: All governance decisions are audited
    Given a governance engine with audit logging to a file
    When 3 actions are checked
    Then the audit log should contain 3 entries
    And the file should be readable after reload
