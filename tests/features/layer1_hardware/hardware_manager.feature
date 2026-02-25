Feature: Hardware Manager
  The HardwareManager coordinates the device registry and safety
  checker to execute commands safely.

  Background:
    Given the device registry is initialized
    And the safety checker is initialized
    And the hardware manager is initialized

  Scenario: Manager exposes registry property
    Then the manager registry is the same registry

  Scenario: Manager exposes safety property
    Then the manager safety checker is the same checker

  Scenario: Execute safe command returns passing result
    Given device "cam-mgr" is registered with status "online"
    When I execute command "capture" on device "cam-mgr" via manager
    Then the command execution result passes
    And the command execution level is "safe"
    And an event "hardware.command.executed" is emitted

  Scenario: Execute command on offline device returns blocked result
    Given device "cam-off" is registered with status "offline"
    When I execute command "capture" on device "cam-off" via manager
    Then the command execution result fails
    And the command execution level is "blocked"
    And an event "hardware.command.executed" is emitted

  Scenario: Execute command on error device returns blocked result
    Given device "cam-err" is registered with status "error"
    When I execute command "capture" on device "cam-err" via manager
    Then the command execution result fails
    And the command execution level is "blocked"

  Scenario: Execute command on calibrating device returns blocked result
    Given device "cam-cal" is registered with status "calibrating"
    When I execute command "acquire" on device "cam-cal" via manager
    Then the command execution result fails
    And the command execution level is "blocked"

  Scenario: Execute command on nonexistent device returns blocked result
    When I execute command "capture" on device "ghost-mgr" via manager
    Then the command execution result fails
    And the command execution level is "blocked"

  Scenario: Execute command on in_use device returns passing result
    Given device "cam-busy" is registered with status "in_use"
    When I execute command "capture" on device "cam-busy" via manager
    Then the command execution result passes
    And the command execution level is "safe"

  Scenario: Execute command with parameters passes safely
    Given device "cam-params" is registered with status "online"
    When I execute command "capture" with parameters on device "cam-params" via manager
    Then the command execution result passes
