Feature: Device Registry
  The system maintains a registry of all lab devices with their
  capabilities, status, and configuration.

  Background:
    Given the device registry is initialized

  Scenario: Register a new device
    When I register a device "cam-001" of type "camera" with status "online"
    Then the registry contains device "cam-001"
    And device "cam-001" has status "online"
    And an event "hardware.device.registered" is emitted

  Scenario: Update device status
    Given device "scope-001" is registered with status "online"
    When I update device "scope-001" status to "calibrating"
    Then device "scope-001" has status "calibrating"
    And an event "hardware.device.status_changed" is emitted

  Scenario: List devices filtered by status
    Given device "cam-001" is registered with status "online"
    And device "cam-002" is registered with status "offline"
    And device "scope-001" is registered with status "online"
    When I list devices with status "online"
    Then I get 2 devices

  Scenario: Get nonexistent device raises error
    When I get device "nonexistent"
    Then a KeyError is raised

  Scenario: Unregister a device
    Given device "old-cam" is registered with status "offline"
    When I unregister device "old-cam"
    Then the registry does not contain device "old-cam"
    And an event "hardware.device.unregistered" is emitted
