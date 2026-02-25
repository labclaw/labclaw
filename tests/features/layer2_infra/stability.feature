Feature: Production Stability (v0.0.9)
  The system recovers from crashes and provides monitoring.

  Scenario: State is saved and recovered after restart
    Given a daemon with 5 completed cycles
    When the daemon state is saved
    And the daemon is restarted
    Then the recovered state shows 5 completed cycles

  Scenario: Corrupt state file is handled gracefully
    Given a corrupt state file
    When the daemon starts
    Then it initializes fresh state without error

  Scenario: Health endpoint shows component status
    Given a running API server
    When I check the health endpoint
    Then all components show status
    And uptime is reported

  Scenario: JSON logging produces structured output
    Given structured logging is configured
    When a log message is emitted
    Then the output is valid JSON with timestamp and level

  Scenario: Atomic state write survives interruption
    Given a state file being written
    When the write is interrupted
    Then the previous state file is intact
