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

  Scenario: Postdoc can execute actions
    Given a governance engine with default role permissions
    When a postdoc requests to "execute" an action
    Then the decision should be allowed

  Scenario: Postdoc can approve actions
    Given a governance engine with default role permissions
    When a postdoc requests to "approve" an action
    Then the decision should be allowed

  Scenario: Graduate student can execute actions
    Given a governance engine with default role permissions
    When a graduate student requests to "execute" an action
    Then the decision should be allowed

  Scenario: Graduate student cannot approve actions
    Given a governance engine with default role permissions
    When a graduate student requests to "approve" an action
    Then the decision should be denied

  Scenario: Undergraduate can read data
    Given a governance engine with default role permissions
    When an undergraduate requests to "read" an action
    Then the decision should be allowed

  Scenario: Undergraduate can write data
    Given a governance engine with default role permissions
    When an undergraduate requests to "write" an action
    Then the decision should be allowed

  Scenario: Digital intern can only read
    Given a governance engine with default role permissions
    When a digital intern requests to "read" an action
    Then the decision should be allowed

  Scenario: Digital intern cannot execute
    Given a governance engine with default role permissions
    When a digital intern requests to "execute" an action
    Then the decision should be denied

  Scenario: Digital analyst can analyze
    Given a governance engine with default role permissions
    When a digital analyst requests to "analyze" an action
    Then the decision should be allowed

  Scenario: Digital analyst cannot execute
    Given a governance engine with default role permissions
    When a digital analyst requests to "execute" an action
    Then the decision should be denied

  Scenario: Multiple safety rules are checked in sequence
    Given a governance engine with multiple safety rules
    When a pi requests a blocked action "danger_action"
    Then the decision should be denied

  Scenario: Audit log entry has required fields
    Given a governance engine with default role permissions
    When the PI requests to "read" an action
    Then the audit entry has actor, action, decision, and timestamp

  Scenario: Audit log accumulates entries across multiple checks
    Given a governance engine with default role permissions
    When I check 5 different actions as PI
    Then the audit log should contain 5 entries total

  Scenario: Safety rule with require_approval_if allows with approval needed
    Given a governance engine with a require_approval_if rule for "deploy"
    When the PI requests to "deploy" an action
    Then the decision should be allowed
    And the decision requires approval

  Scenario: Custom role permissions deny unknown role
    Given a governance engine with default role permissions
    When an unknown role requests to "execute" an action
    Then the decision should be denied
