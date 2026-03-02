Feature: Proactive Engine (L2)
  The proactive engine enables autonomous behavior by monitoring events,
  firing triggers, and tracking commitments for 7x24 always-on capability.

  Scenario: Register and fire a trigger on matching event
    Given a proactive engine
    And a trigger "data-alert" matching "infra.test.action"
    When the event "infra.test.action" occurs
    Then the trigger "data-alert" fires

  Scenario: Trigger does not fire on non-matching event
    Given a proactive engine
    And a trigger "no-match" matching "memory.graph.*"
    When the event "infra.test.action" occurs
    Then no triggers fire

  Scenario: Wildcard pattern matches any event
    Given a proactive engine
    And a trigger "catch-all" matching "*"
    When the event "memory.graph.updated" occurs
    Then the trigger "catch-all" fires

  Scenario: Disabled trigger does not fire
    Given a proactive engine
    And a disabled trigger "off" matching "*"
    When the event "infra.test.action" occurs
    Then no triggers fire

  Scenario: Cooldown prevents repeated firing
    Given a proactive engine
    And a trigger "cooldown" matching "*" with cooldown 3600 seconds
    When the event "infra.test.action" occurs twice
    Then the trigger fires only once

  Scenario: Condition filters events by payload
    Given a proactive engine
    And a trigger "big-data" matching "infra.*.*" with condition "payload.get('size', 0) > 100"
    When the event "infra.test.action" occurs with size 50
    Then no triggers fire
    When the event "infra.test.action" occurs with size 200
    Then the trigger "big-data" fires

  Scenario: Track and fulfill a commitment
    Given a proactive engine
    And a commitment "Submit paper" is added
    When I fulfill the commitment
    Then the commitment status is "fulfilled"

  Scenario: Detect overdue commitment
    Given a proactive engine
    And a commitment "Late report" due 1 hour ago
    When I check commitments
    Then the commitment is overdue

  Scenario: Future commitment is not overdue
    Given a proactive engine
    And a commitment "Future task" due in 24 hours
    When I check commitments
    Then no commitments are overdue

  Scenario: Remove a trigger
    Given a proactive engine
    And a trigger "removable" matching "*"
    When I remove the trigger "removable"
    Then no triggers are registered
