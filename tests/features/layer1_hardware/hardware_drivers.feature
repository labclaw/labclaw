Feature: Concrete Hardware Drivers
  Concrete driver implementations parse device-specific file formats
  and handle error conditions gracefully.

  # ---------------------------------------------------------------------------
  # PlateReaderCSVDriver
  # ---------------------------------------------------------------------------

  Scenario: PlateReaderCSVDriver parses 96-well grid data
    Given a temporary watch directory exists
    And a plate reader CSV file "plate.csv" with row "A" values "0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2"
    When I parse that plate CSV file with PlateReaderCSVDriver
    Then the parsed plate data contains wells "A1" through "A12"
    And well "A1" has value 0.1
    And well "A12" has value 1.2

  Scenario: PlateReaderCSVDriver parses metadata rows
    Given a temporary watch directory exists
    And a plate reader CSV file "plate_meta.csv" with metadata "Instrument,BioTek Synergy"
    When I parse that plate CSV file with PlateReaderCSVDriver
    Then the parsed plate metadata contains key "Instrument" with value "BioTek Synergy"

  Scenario: PlateReaderCSVDriver ignores columns beyond 12
    Given a temporary watch directory exists
    And a plate reader CSV file "plate_extra.csv" with row "B" having 14 values
    When I parse that plate CSV file with PlateReaderCSVDriver
    Then the parsed plate data has at most 12 wells for row "B"

  Scenario: PlateReaderCSVDriver handles non-numeric well values as strings
    Given a temporary watch directory exists
    And a plate reader CSV file "plate_str.csv" with row "C" values "N/A,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2,1.3,1.4,1.5"
    When I parse that plate CSV file with PlateReaderCSVDriver
    Then well "C1" is stored as a string

  Scenario: PlateReaderCSVDriver handles empty file gracefully
    Given a temporary watch directory exists
    And an empty plate reader CSV file "empty_plate.csv"
    When I parse that plate CSV file with PlateReaderCSVDriver
    Then the parsed plate data has 0 wells

  Scenario: PlateReaderCSVDriver default file pattern is CSV only
    Given a temporary watch directory exists
    When I create a PlateReaderCSVDriver for that directory
    Then the PlateReaderCSVDriver file patterns include "*.csv"

  Scenario: PlateReaderCSVDriver result includes file path
    Given a temporary watch directory exists
    And a plate reader CSV file "plate_path.csv" with row "A" values "0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2"
    When I parse that plate CSV file with PlateReaderCSVDriver
    Then the parsed plate result includes key "file"

  # ---------------------------------------------------------------------------
  # QPCRExportDriver
  # ---------------------------------------------------------------------------

  Scenario: QPCRExportDriver parses sample rows from results block
    Given a temporary watch directory exists
    And a qPCR export file "qpcr.txt" with results header and one sample row
    When I parse that qPCR file with QPCRExportDriver
    Then the parsed qPCR data contains 1 sample

  Scenario: QPCRExportDriver parses Ct value as float
    Given a temporary watch directory exists
    And a qPCR export file "qpcr_ct.txt" with a sample having ct value "22.45"
    When I parse that qPCR file with QPCRExportDriver
    Then the parsed sample has ct value 22.45

  Scenario: QPCRExportDriver treats UNDETERMINED ct as string
    Given a temporary watch directory exists
    And a qPCR export file "qpcr_und.txt" with a sample having ct value "UNDETERMINED"
    When I parse that qPCR file with QPCRExportDriver
    Then the parsed sample has ct value "UNDETERMINED"

  Scenario: QPCRExportDriver parses metadata before results block
    Given a temporary watch directory exists
    And a qPCR export file "qpcr_meta.txt" with metadata "Experiment Name\tMyExperiment" and a sample row
    When I parse that qPCR file with QPCRExportDriver
    Then the parsed qPCR metadata contains key "Experiment Name" with value "MyExperiment"

  Scenario: QPCRExportDriver stops parsing at blank line after results
    Given a temporary watch directory exists
    And a qPCR export file "qpcr_stop.txt" with two sample rows then a blank line and trailing data
    When I parse that qPCR file with QPCRExportDriver
    Then the parsed qPCR data contains 2 samples

  Scenario: QPCRExportDriver handles empty file gracefully
    Given a temporary watch directory exists
    And an empty qPCR export file "empty_qpcr.txt"
    When I parse that qPCR file with QPCRExportDriver
    Then the parsed qPCR data contains 0 samples

  Scenario: QPCRExportDriver default file patterns include txt tsv and csv
    Given a temporary watch directory exists
    When I create a QPCRExportDriver for that directory
    Then the QPCRExportDriver file patterns include "*.txt"
    And the QPCRExportDriver file patterns include "*.tsv"
    And the QPCRExportDriver file patterns include "*.csv"

  Scenario: QPCRExportDriver result includes file path
    Given a temporary watch directory exists
    And a qPCR export file "qpcr_fpath.txt" with results header and one sample row
    When I parse that qPCR file with QPCRExportDriver
    Then the parsed qPCR result includes key "file"

  # ---------------------------------------------------------------------------
  # FileWatcherDriver
  # ---------------------------------------------------------------------------

  Scenario: FileWatcherDriver connect starts observer when directory exists
    Given a temporary watch directory exists
    When I create a FileWatcherDriver for that directory
    And I connect the FileWatcherDriver
    Then the FileWatcherDriver is connected
    And I disconnect the FileWatcherDriver to clean up

  Scenario: FileWatcherDriver connect fails when directory does not exist
    When I create a FileWatcherDriver for a nonexistent directory
    And I connect the FileWatcherDriver
    Then the FileWatcherDriver connection fails

  Scenario: FileWatcherDriver status is offline when not connected
    Given a temporary watch directory exists
    When I create a FileWatcherDriver for that directory
    And I check FileWatcherDriver status
    Then the FileWatcherDriver status is "offline"

  Scenario: FileWatcherDriver read returns empty when handler is not initialized
    Given a temporary watch directory exists
    When I create a FileWatcherDriver for that directory
    And I read from the FileWatcherDriver without connecting
    Then the watcher read result has 0 new files

  Scenario: FileWatcherDriver disconnect stops observer
    Given a temporary watch directory exists
    When I create a FileWatcherDriver for that directory
    And I connect the FileWatcherDriver
    And I disconnect the FileWatcherDriver
    Then an event "hardware.driver.disconnected" is emitted

  Scenario: FileWatcherDriver inherits parse_file from FileBasedDriver
    Given a temporary watch directory exists
    And a CSV file "watcher.csv" exists in that directory with header "a,b" and row "1,2"
    When I create a FileWatcherDriver for that directory
    And I parse "watcher.csv" with the FileWatcherDriver
    Then the parsed data contains key "rows"
