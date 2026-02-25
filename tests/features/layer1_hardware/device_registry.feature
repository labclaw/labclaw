Feature: Device Registry
  The system maintains a registry of all lab devices with their
  capabilities, status, and configuration.

  Background:
    Given the device registry is initialized

  # ---------------------------------------------------------------------------
  # Registration — happy paths
  # ---------------------------------------------------------------------------

  Scenario: Register a new device
    When I register a device "cam-001" of type "camera" with status "online"
    Then the registry contains device "cam-001"
    And device "cam-001" has status "online"
    And an event "hardware.device.registered" is emitted

  Scenario: Register device with status offline
    When I register a device "scope-001" of type "microscope" with status "offline"
    Then the registry contains device "scope-001"
    And device "scope-001" has status "offline"

  Scenario: Register device with status calibrating
    When I register a device "cam-002" of type "camera" with status "calibrating"
    Then the registry contains device "cam-002"
    And device "cam-002" has status "calibrating"

  Scenario: Register device with status error
    When I register a device "daq-001" of type "daq" with status "error"
    Then the registry contains device "daq-001"
    And device "daq-001" has status "error"

  Scenario: Register device with status maintenance
    When I register a device "reader-001" of type "plate_reader" with status "in_use"
    Then the registry contains device "reader-001"
    And device "reader-001" has status "in_use"

  Scenario: Register device with capabilities metadata
    When I register a device "cam-cap" of type "camera" with status "online" and capabilities "capture,stream"
    Then the registry contains device "cam-cap"
    And device "cam-cap" has capability "capture"
    And device "cam-cap" has capability "stream"

  Scenario: Register device has all required fields
    When I register a device "test-device" of type "sensor" with status "online"
    Then the registered device has field "device_id"
    And the registered device has field "name"
    And the registered device has field "device_type"
    And the registered device has field "status"
    And the registered device has field "registered_at"

  Scenario: Register two devices with same name succeeds (different IDs)
    When I register a device "cam-001" of type "camera" with status "online"
    And I register a second device "cam-001" of type "camera" with status "offline"
    Then both devices are in the registry with different IDs

  Scenario: Register duplicate device ID raises ValueError
    Given device "scope-dup" is registered with status "online"
    When I re-register device "scope-dup" with the same ID
    Then a ValueError is raised

  # ---------------------------------------------------------------------------
  # Status updates
  # ---------------------------------------------------------------------------

  Scenario: Update device status
    Given device "scope-001" is registered with status "online"
    When I update device "scope-001" status to "calibrating"
    Then device "scope-001" has status "calibrating"
    And an event "hardware.device.status_changed" is emitted

  Scenario: Update device status from offline to online
    Given device "cam-003" is registered with status "offline"
    When I update device "cam-003" status to "online"
    Then device "cam-003" has status "online"

  Scenario: Update device status from online to error
    Given device "daq-002" is registered with status "online"
    When I update device "daq-002" status to "error"
    Then device "daq-002" has status "error"

  Scenario: Update device status to in_use
    Given device "reader-002" is registered with status "online"
    When I update device "reader-002" status to "in_use"
    Then device "reader-002" has status "in_use"

  Scenario: Update nonexistent device raises KeyError
    When I update status of nonexistent device "ghost-001" to "online"
    Then an update status KeyError is raised

  # ---------------------------------------------------------------------------
  # List / query
  # ---------------------------------------------------------------------------

  Scenario: List devices filtered by status
    Given device "cam-001" is registered with status "online"
    And device "cam-002" is registered with status "offline"
    And device "scope-001" is registered with status "online"
    When I list devices with status "online"
    Then I get 2 devices

  Scenario: List all devices without filter
    Given device "cam-001" is registered with status "online"
    And device "cam-002" is registered with status "offline"
    And device "scope-001" is registered with status "calibrating"
    When I list all devices
    Then I get 3 devices

  Scenario: List devices when registry is empty
    When I list all devices
    Then I get 0 devices

  Scenario: List devices with status that has no matches
    Given device "cam-001" is registered with status "online"
    When I list devices with status "error"
    Then I get 0 devices

  # ---------------------------------------------------------------------------
  # Get / lookup
  # ---------------------------------------------------------------------------

  Scenario: Get nonexistent device raises error
    When I get device "nonexistent"
    Then a KeyError is raised

  # ---------------------------------------------------------------------------
  # Unregister
  # ---------------------------------------------------------------------------

  Scenario: Unregister a device
    Given device "old-cam" is registered with status "offline"
    When I unregister device "old-cam"
    Then the registry does not contain device "old-cam"
    And an event "hardware.device.unregistered" is emitted

  Scenario: Unregister nonexistent device raises KeyError
    When I unregister nonexistent device "ghost-002"
    Then an unregister KeyError is raised
