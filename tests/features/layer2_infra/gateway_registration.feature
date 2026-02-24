Feature: Gateway Registration
  Devices and agents connect to the gateway and register themselves.

  Background:
    Given the gateway is initialized

  Scenario: Register a device client
    When I register a client "cam-001" of type "device"
    Then the gateway has 1 connection
    And the connection has client_id "cam-001"
    And an event "infra.gateway.client_registered" is emitted

  Scenario: Register multiple clients
    When I register a client "cam-001" of type "device"
    And I register a client "analyzer-001" of type "agent"
    Then the gateway has 2 connections

  Scenario: Unregister a client
    Given client "cam-001" of type "device" is registered
    When I unregister client "cam-001"
    Then the gateway has 0 connections
    And an event "infra.gateway.client_disconnected" is emitted

  Scenario: Send a targeted message
    Given client "cam-001" of type "device" is registered
    And client "analyzer-001" of type "agent" is registered
    When I send a message from "cam-001" to "analyzer-001" with type "event"
    Then the message is routed successfully
    And an event "infra.gateway.message_routed" is emitted

  Scenario: Broadcast a message
    Given client "cam-001" of type "device" is registered
    And client "cam-002" of type "device" is registered
    When I broadcast a message from "system" with type "event"
    Then the message reaches all connected clients
