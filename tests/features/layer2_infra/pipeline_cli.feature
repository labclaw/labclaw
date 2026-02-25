Feature: Pipeline CLI Command
  The labclaw pipeline command runs one discovery cycle on CSV data.

  Scenario: Pipeline command runs on CSV data
    Given a data directory with behavioral CSV files
    When I run "labclaw pipeline --once --data-dir DATA_DIR"
    Then the output is valid JSON
    And the result shows success

  Scenario: Pipeline command with --seed produces deterministic output
    Given a data directory with behavioral CSV files
    When I run the pipeline command twice with --seed 42
    Then both results have the same patterns_found count

  Scenario: Pipeline command with no data directory shows error
    When I run "labclaw pipeline" with no data directory
    Then the command exits with an error

  Scenario: Pipeline command on empty directory shows error
    Given an empty data directory
    When I run "labclaw pipeline --once --data-dir EMPTY_DIR"
    Then the command exits with an error

  Scenario: Pipeline command without --memory-root succeeds
    Given a data directory with behavioral CSV files
    When I run the pipeline command without a memory root
    Then the output is valid JSON
    And the result shows success

  Scenario: Pipeline --help prints usage information
    When I run "labclaw pipeline --help"
    Then the output contains "data-dir"
