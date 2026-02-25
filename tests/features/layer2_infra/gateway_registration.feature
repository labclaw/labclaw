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

  Scenario: Register client with duplicate ID overwrites old connection
    When I register a client "dup-client" of type "device"
    And I register a client "dup-client" of type "agent"
    Then the gateway has 1 connection
    And the connection type is "agent"

  Scenario: Send message to nonexistent client raises error
    When I try to send a message to nonexistent client "ghost-001"
    Then a KeyError is raised

  Scenario: Broadcast with no clients registered completes without error
    When I broadcast a message from "system" with type "ping"
    Then no gateway exception is raised

  Scenario: Register client of type "agent"
    When I register a client "agent-001" of type "agent"
    Then the gateway has 1 connection
    And the connection has client_id "agent-001"

  Scenario: Register client of type "dashboard"
    When I register a client "dashboard-001" of type "dashboard"
    Then the gateway has 1 connection
    And the connection has client_id "dashboard-001"

  Scenario: List all connected clients
    When I register a client "cam-001" of type "device"
    And I register a client "agent-001" of type "agent"
    And I register a client "dash-001" of type "dashboard"
    Then the gateway has 3 connections

  Scenario: Gateway connection has metadata fields
    When I register a client "meta-client" of type "device"
    Then the connection has a connection_id
    And the connection has a connected_at timestamp

  Scenario: Get connection by connection_id
    When I register a client "lookup-001" of type "device"
    Then I can retrieve the connection by its connection_id
