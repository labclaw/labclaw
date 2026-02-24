Feature: Event Bus
  All system events flow through the event bus with pub/sub.

  Background:
    Given the event bus is initialized

  Scenario: Publish and receive an event
    Given a subscriber listening for "memory.tier_a.updated"
    When I publish an event "memory.tier_a.updated" with payload key "entity_id" value "lab-001"
    Then the subscriber receives the event
    And the event payload contains "entity_id"

  Scenario: Wildcard subscriber receives all events
    Given a wildcard subscriber listening for all events
    When I publish an event "hardware.device.registered"
    And I publish an event "memory.tier_a.updated"
    Then the wildcard subscriber received 2 events

  Scenario: Unsubscribe stops receiving events
    Given a subscriber listening for "hardware.device.registered"
    When I unsubscribe from "hardware.device.registered"
    And I publish an event "hardware.device.registered"
    Then the subscriber received 0 events
