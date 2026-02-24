Feature: Sentinel Quality Monitoring (OBSERVE + ANALYZE)
  The system monitors data quality and raises alerts when
  quality degrades below configured thresholds.

  Background:
    Given the sentinel is initialized

  Scenario: Check a good quality metric
    Given a rule "min_file_size" for metric "file_size" below threshold 100
    When I check a metric "file_size" with value 500
    Then no alerts are raised
    And an event "sentinel.check.completed" is emitted

  Scenario: Check triggers alert on low quality
    Given a rule "min_file_size" for metric "file_size" below threshold 100
    When I check a metric "file_size" with value 50
    Then 1 alert is raised with level "warning"
    And an event "sentinel.alert.raised" is emitted

  Scenario: Session quality summary - all good
    Given a rule "min_snr" for metric "snr" below threshold 3.0
    When I check session "sess-001" with metrics:
      | name     | value |
      | snr      | 5.0   |
      | snr      | 4.5   |
    Then the session summary overall level is "good"
    And the session has 0 alerts

  Scenario: Session quality summary - degraded
    Given a rule "min_snr" for metric "snr" below threshold 3.0
    When I check session "sess-002" with metrics:
      | name     | value |
      | snr      | 5.0   |
      | snr      | 2.0   |
    Then the session summary overall level is "warning"
    And the session has 1 alert

  Scenario: Retrieve alerts filtered by session
    Given a rule "min_snr" for metric "snr" below threshold 3.0
    And I check session "sess-001" with a passing metric
    And I check session "sess-002" with a failing metric
    When I get alerts for session "sess-002"
    Then I get 1 alert
