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

  Scenario: Register event type in registry
    When I register event type "infra.bus.heartbeat"
    Then the event type "infra.bus.heartbeat" is registered

  Scenario: Publish event with nested dict payload
    Given a subscriber listening for "discovery.mining.complete"
    When I publish an event "discovery.mining.complete" with nested payload
    Then the subscriber receives the event
    And the event payload contains "results"

  Scenario: Subscribe same handler to multiple events
    Given a subscriber listening for "hardware.device.registered"
    And a subscriber listening for "hardware.device.offline"
    When I publish an event "hardware.device.registered"
    And I publish an event "hardware.device.offline"
    Then the subscriber received 2 events

  Scenario: Publish to event with no subscribers causes no error
    When I publish an event "infra.test.orphan" with no subscribers
    Then no exception is raised

  Scenario: Event names follow layer.module.action pattern
    When I create an event with name "memory.tier_a.updated"
    Then the event has layer "memory" module "tier_a" action "updated"

  Scenario: List all registered events
    When I register event type "infra.bus.tick"
    Then the event registry lists at least 1 event

  Scenario: Event has timestamp and source_id fields
    Given a subscriber listening for "infra.bus.probe"
    When I publish an event "infra.bus.probe" with payload key "x" value "1"
    Then the event has a timestamp
    And the event has an event_id

  Scenario: Invalid event name format raises error
    When I try to register an event with invalid name "bad_name"
    Then a ValueError is raised

  Scenario: Invalid event name with only two parts raises error
    When I try to register an event with invalid name "layer.module"
    Then a ValueError is raised
