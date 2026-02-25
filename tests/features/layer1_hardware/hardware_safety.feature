Feature: Hardware Safety
  Every hardware command passes through safety validation
  before execution.

  Background:
    Given the device registry is initialized
    And the safety checker is initialized

  # ---------------------------------------------------------------------------
  # Online device — safe commands
  # ---------------------------------------------------------------------------

  Scenario: Safe command on online device passes
    Given device "cam-001" is registered with status "online"
    When I check safety for command "capture" on device "cam-001"
    Then the safety check passes
    And the safety level is "safe"
    And an event "hardware.safety.checked" is emitted

  Scenario: Safe command on in_use device passes
    Given device "cam-in-use" is registered with status "in_use"
    When I check safety for command "capture" on device "cam-in-use"
    Then the safety check passes
    And the safety level is "safe"

  # ---------------------------------------------------------------------------
  # Blocked statuses
  # ---------------------------------------------------------------------------

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

  Scenario: Command on calibrating device is blocked
    Given device "cal-cam" is registered with status "calibrating"
    When I check safety for command "capture" on device "cal-cam"
    Then the safety check fails
    And the safety level is "blocked"

  Scenario: Command on reserved device is blocked
    Given device "reserved-scope" is registered with status "reserved"
    When I check safety for command "start_imaging" on device "reserved-scope"
    Then the safety check fails
    And the safety level is "blocked"

  # ---------------------------------------------------------------------------
  # Nonexistent device
  # ---------------------------------------------------------------------------

  Scenario: Safety check on nonexistent device fails
    When I check safety for command "capture" on device "nonexistent"
    Then the safety check fails
    And the safety level is "blocked"

  # ---------------------------------------------------------------------------
  # Capability checks
  # ---------------------------------------------------------------------------

  Scenario: Command within device capabilities passes
    Given device "cam-cap" is registered with status "online" and capabilities "capture,stream"
    When I check safety for command "capture" on device "cam-cap"
    Then the safety check passes
    And the safety level is "safe"

  Scenario: Command outside device capabilities is blocked
    Given device "cam-cap2" is registered with status "online" and capabilities "capture"
    When I check safety for command "start_imaging" on device "cam-cap2"
    Then the safety check fails
    And the safety level is "blocked"

  Scenario: Device with no capabilities allows any command
    Given device "cam-nocap" is registered with status "online"
    When I check safety for command "any_action" on device "cam-nocap"
    Then the safety check passes

  # ---------------------------------------------------------------------------
  # Multiple checks and history
  # ---------------------------------------------------------------------------

  Scenario: Multiple safety checks are recorded in history
    Given device "cam-hist" is registered with status "online"
    When I check safety for command "capture" on device "cam-hist"
    And I check safety for command "capture" on device "cam-hist"
    And I check safety for command "capture" on device "cam-hist"
    Then the safety history for device "cam-hist" has 3 entries

  Scenario: Safety history is per-device
    Given device "cam-a" is registered with status "online"
    And device "cam-b" is registered with status "online"
    When I check safety for command "capture" on device "cam-a"
    And I check safety for command "capture" on device "cam-b"
    And I check safety for command "capture" on device "cam-b"
    Then the safety history for device "cam-a" has 1 entries
    And the safety history for device "cam-b" has 2 entries

  # ---------------------------------------------------------------------------
  # Manager — command execution
  # ---------------------------------------------------------------------------

  Scenario: Execute safe command via manager emits command executed event
    Given the hardware manager is initialized
    And device "exec-cam" is registered with status "online"
    When I execute command "capture" on device "exec-cam" via manager
    Then the command execution result passes
    And an event "hardware.command.executed" is emitted

  Scenario: Execute blocked command via manager does not execute
    Given the hardware manager is initialized
    And device "blocked-cam" is registered with status "offline"
    When I execute command "capture" on device "blocked-cam" via manager
    Then the command execution result fails
    And an event "hardware.command.executed" is emitted
