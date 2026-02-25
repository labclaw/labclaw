Feature: Session Chronicle (OBSERVE)
  The system monitors directories for new data files, performs
  quality checks, and assembles session records.

  Background:
    Given the session chronicle is initialized
    And the edge watcher is initialized

  Scenario: Detect a new file in watched directory
    Given a watched directory for device "cam-001"
    When a new file "recording_001.avi" appears in the directory
    Then the file is detected
    And an event "hardware.file.detected" is emitted with device_id "cam-001"

  Scenario: Start and end a session
    When I start a session with operator "alice"
    Then a SessionNode is created
    And an event "session.chronicle.started" is emitted
    When I add a recording with modality "video" and file "rec_001.avi"
    Then the session has 1 recording
    And an event "session.recording.added" is emitted
    When I end the session
    Then the session has a duration
    And an event "session.chronicle.ended" is emitted

  Scenario: Quality check on an existing file
    Given a file "test_data.csv" with 100 bytes of content
    When I run a quality check on the file
    Then the quality check returns metrics
    And the quality level is "good"

  Scenario: Quality check on empty file warns
    Given an empty file "bad_data.csv"
    When I run a quality check on the file
    Then the quality level is "warning"

  Scenario: List all sessions
    Given 3 completed sessions
    When I list all sessions
    Then I get 3 sessions

  Scenario: Multiple recordings in one session
    When I start a session with operator "bob"
    And I add a recording with modality "video" and file "rec_a.avi"
    And I add a recording with modality "ephys" and file "rec_b.nwb"
    Then the session has 2 recordings

  Scenario: Session with no recordings ends cleanly
    When I start a session with operator "carol"
    Then a SessionNode is created
    When I end the session
    Then the session has a duration
    And the session has 0 recordings

  Scenario: Quality check on large file returns good level
    Given a file "large_data.bin" with 1048576 bytes of content
    When I run a quality check on the file
    Then the quality level is "good"

  Scenario: File detection with supported video extension
    Given a watched directory for device "cam-002"
    When a new file "recording_002.mp4" appears in the directory
    Then the file is detected

  Scenario: File detection ignores dotfiles
    Given a watched directory for device "cam-003"
    When a new file ".hidden_file.avi" appears in the directory
    Then the hidden file is not detected as a valid recording
