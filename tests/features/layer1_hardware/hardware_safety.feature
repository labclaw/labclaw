Feature: Hardware Safety
  Every hardware command passes through safety validation
  before execution.

  Background:
    Given the device registry is initialized
    And the safety checker is initialized

  Scenario: Safe command on online device passes
    Given device "cam-001" is registered with status "online"
    When I check safety for command "capture" on device "cam-001"
    Then the safety check passes
    And the safety level is "safe"
    And an event "hardware.safety.checked" is emitted

  Scenario: Command on offline device is blocked
    Given device "cam-002" is registered with status "offline"
    When I check safety for command "capture" on device "cam-002"
    Then the safety check fails
    And the safety level is "blocked"

  Scenario: Command on device in error state is blocked
    Given device "scope-001" is registered with status "error"
    When I check safety for command "start_imaging" on device "scope-001"
    Then the safety check fails
    And the safety level is "blocked"

  Scenario: Safety check on nonexistent device fails
    When I check safety for command "capture" on device "nonexistent"
    Then the safety check fails
