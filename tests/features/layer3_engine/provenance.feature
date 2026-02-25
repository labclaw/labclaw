Feature: Full Provenance Chains (C4: TRACE)
  Every finding has a complete chain from raw data to conclusion.

  Scenario: Pipeline produces provenance for each finding
    Given behavioral data from fixtures
    When I run a full discovery cycle with provenance tracking
    Then every finding has a provenance chain
    And each chain starts from the data source

  Scenario: NWB export includes provenance
    Given a completed discovery cycle with findings
    When I export to NWB format
    Then the export file contains provenance metadata

  Scenario: Provenance chain can be verified
    Given a finding with a provenance chain
    When I verify the chain
    Then all steps are present and connected

  Scenario: Export to JSON when pynwb is not available
    Given a completed discovery cycle
    When I export with NWB format but pynwb is unavailable
    Then a JSON fallback file is created
