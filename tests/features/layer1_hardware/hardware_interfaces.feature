Feature: Hardware Interface Drivers
  Each hardware interface driver implements the DeviceDriver protocol:
  connect/disconnect lifecycle and read/write I/O.

  # ---------------------------------------------------------------------------
  # FileBasedDriver
  # ---------------------------------------------------------------------------

  Scenario: FileBasedDriver connect succeeds when directory exists
    Given a temporary watch directory exists
    When I create a FileBasedDriver for that directory
    And I connect the FileBasedDriver
    Then the FileBasedDriver is connected
    And an event "hardware.driver.connected" is emitted

  Scenario: FileBasedDriver connect fails when directory does not exist
    When I create a FileBasedDriver for a nonexistent directory
    And I connect the FileBasedDriver
    Then the FileBasedDriver connection fails
    And an event "hardware.driver.error" is emitted

  Scenario: FileBasedDriver connect fails when path is a file not a directory
    Given a temporary file exists at watch path
    When I create a FileBasedDriver for that file path
    And I connect the FileBasedDriver
    Then the FileBasedDriver connection fails

  Scenario: FileBasedDriver disconnect sets connected to false
    Given a temporary watch directory exists
    When I create a FileBasedDriver for that directory
    And I connect the FileBasedDriver
    And I disconnect the FileBasedDriver
    Then an event "hardware.driver.disconnected" is emitted

  Scenario: FileBasedDriver status is online when connected
    Given a temporary watch directory exists
    When I create a FileBasedDriver for that directory
    And I connect the FileBasedDriver
    And I check FileBasedDriver status
    Then the FileBasedDriver status is "online"

  Scenario: FileBasedDriver status is offline when not connected
    Given a temporary watch directory exists
    When I create a FileBasedDriver for that directory
    And I check FileBasedDriver status
    Then the FileBasedDriver status is "offline"

  Scenario: FileBasedDriver read finds new CSV file
    Given a temporary watch directory exists
    When I create a FileBasedDriver for that directory
    And I connect the FileBasedDriver
    And a CSV file "data.csv" is created in the watch directory with content "col1,col2\n1,2\n"
    And I read from the FileBasedDriver
    Then the read result contains 1 new file

  Scenario: FileBasedDriver read returns empty when no new files
    Given a temporary watch directory exists
    When I create a FileBasedDriver for that directory
    And I connect the FileBasedDriver
    And I read from the FileBasedDriver
    Then the read result contains 0 new files

  Scenario: FileBasedDriver write always returns False
    Given a temporary watch directory exists
    When I create a FileBasedDriver for that directory
    And I connect the FileBasedDriver
    And I write command "noop" to the FileBasedDriver
    Then the FileBasedDriver write returns False

  Scenario: FileBasedDriver parse_file returns row data for CSV
    Given a temporary watch directory exists
    And a CSV file "sample.csv" exists in that directory with header "well,value" and row "A1,0.5"
    When I create a FileBasedDriver for that directory
    And I parse "sample.csv" with the FileBasedDriver
    Then the parsed data contains key "rows"
    And the parsed data has row count 1

  # ---------------------------------------------------------------------------
  # NetworkAPIDriver
  # ---------------------------------------------------------------------------

  Scenario: NetworkAPIDriver exposes device_id property
    When I create a NetworkAPIDriver with id "net-001" and url "http://localhost:9999"
    Then the NetworkAPIDriver device_id is "net-001"

  Scenario: NetworkAPIDriver exposes device_type property
    When I create a NetworkAPIDriver with id "net-001" type "spectrometer" and url "http://localhost:9999"
    Then the NetworkAPIDriver device_type is "spectrometer"

  Scenario: NetworkAPIDriver status is offline before connect
    When I create a NetworkAPIDriver with id "net-001" and url "http://localhost:9999"
    And I check NetworkAPIDriver status
    Then the NetworkAPIDriver status is "offline"

  Scenario: NetworkAPIDriver disconnect marks driver offline
    When I create a NetworkAPIDriver with id "net-002" and url "http://localhost:9999"
    And I disconnect the NetworkAPIDriver
    Then an event "hardware.driver.disconnected" is emitted

  # ---------------------------------------------------------------------------
  # SerialDriver
  # ---------------------------------------------------------------------------

  Scenario: SerialDriver exposes device_id property
    When I create a SerialDriver with id "ser-001" and port "/dev/ttyUSB0"
    Then the SerialDriver device_id is "ser-001"

  Scenario: SerialDriver exposes device_type property
    When I create a SerialDriver with id "ser-001" type "pump" and port "/dev/ttyUSB0"
    Then the SerialDriver device_type is "pump"

  Scenario: SerialDriver status is offline before connect
    When I create a SerialDriver with id "ser-001" and port "/dev/ttyUSB0"
    And I check SerialDriver status
    Then the SerialDriver status is "offline"

  Scenario: SerialDriver read raises RuntimeError when not connected
    When I create a SerialDriver with id "ser-001" and port "/dev/ttyUSB0"
    And I attempt to read from SerialDriver without connecting
    Then a RuntimeError is raised

  Scenario: SerialDriver parse_response returns raw under response key
    When I create a SerialDriver with id "ser-001" and port "/dev/ttyUSB0"
    And I parse serial response "OK:1.23"
    Then the parsed serial response contains key "response" with value "OK:1.23"

  # ---------------------------------------------------------------------------
  # DAQDriver
  # ---------------------------------------------------------------------------

  Scenario: DAQDriver exposes device_id property
    When I create a DAQDriver with id "daq-001"
    Then the DAQDriver device_id is "daq-001"

  Scenario: DAQDriver exposes device_type property
    When I create a DAQDriver with id "daq-001" type "gpio"
    Then the DAQDriver device_type is "gpio"

  Scenario: DAQDriver status is offline before connect
    When I create a DAQDriver with id "daq-001"
    And I check DAQDriver status
    Then the DAQDriver status is "offline"

  Scenario: DAQDriver connect fails if _open_device raises
    When I create a DAQDriver with id "daq-fail" that raises on open
    And I connect the DAQDriver
    Then the DAQDriver connection fails
    And an event "hardware.driver.error" is emitted

  Scenario: DAQDriver disconnect emits event even if _close_device raises
    When I create a DAQDriver with id "daq-close" that raises on close
    And I connect the DAQDriver successfully
    And I disconnect the DAQDriver
    Then an event "hardware.driver.disconnected" is emitted

  Scenario: DAQDriver write failure returns False
    When I create a DAQDriver with id "daq-write" that raises on write
    And I write command "set_voltage" to the DAQDriver
    Then the DAQDriver write returns False

  # ---------------------------------------------------------------------------
  # SoftwareBridgeDriver
  # ---------------------------------------------------------------------------

  Scenario: SoftwareBridgeDriver exposes device_id property
    When I create a SoftwareBridgeDriver with id "sw-001"
    Then the SoftwareBridgeDriver device_id is "sw-001"

  Scenario: SoftwareBridgeDriver status is offline before connect
    When I create a SoftwareBridgeDriver with id "sw-001"
    And I check SoftwareBridgeDriver status
    Then the SoftwareBridgeDriver status is "offline"

  Scenario: SoftwareBridgeDriver connect fails if _open_connection raises
    When I create a SoftwareBridgeDriver with id "sw-fail" that raises on open
    And I connect the SoftwareBridgeDriver
    Then the SoftwareBridgeDriver connection fails
    And an event "hardware.driver.error" is emitted

  Scenario: SoftwareBridgeDriver disconnect emits event even if _close_connection raises
    When I create a SoftwareBridgeDriver with id "sw-close" that raises on close
    And I connect the SoftwareBridgeDriver successfully
    And I disconnect the SoftwareBridgeDriver
    Then an event "hardware.driver.disconnected" is emitted

  Scenario: SoftwareBridgeDriver write failure returns False
    When I create a SoftwareBridgeDriver with id "sw-write" that raises on send
    And I write command "trigger" to the SoftwareBridgeDriver
    Then the SoftwareBridgeDriver write returns False

  # ---------------------------------------------------------------------------
  # DeviceDriver protocol compliance
  # ---------------------------------------------------------------------------

  Scenario: FileBasedDriver satisfies DeviceDriver protocol
    Given a temporary watch directory exists
    When I create a FileBasedDriver for that directory
    Then the FileBasedDriver satisfies the DeviceDriver protocol

  Scenario: NetworkAPIDriver satisfies DeviceDriver protocol
    When I create a NetworkAPIDriver with id "net-proto" and url "http://localhost"
    Then the NetworkAPIDriver satisfies the DeviceDriver protocol

  Scenario: SerialDriver satisfies DeviceDriver protocol
    When I create a SerialDriver with id "ser-proto" and port "/dev/ttyUSB0"
    Then the SerialDriver satisfies the DeviceDriver protocol

  Scenario: DAQDriver satisfies DeviceDriver protocol
    When I create a DAQDriver with id "daq-proto"
    Then the DAQDriver satisfies the DeviceDriver protocol

  Scenario: SoftwareBridgeDriver satisfies DeviceDriver protocol
    When I create a SoftwareBridgeDriver with id "sw-proto"
    Then the SoftwareBridgeDriver satisfies the DeviceDriver protocol
