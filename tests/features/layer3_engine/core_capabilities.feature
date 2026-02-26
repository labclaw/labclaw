Feature: Core Capabilities
  LabClaw must demonstrate 5 core capabilities.

  Scenario: C1 — Discover statistically significant finding
    Given behavioral session data with embedded correlations
    When a full scientific loop cycle is executed
    Then at least one pattern is discovered
    And at least one finding has p-value less than 0.05

  Scenario: C2 — Evolution improves fitness over 10 cycles
    Given behavioral session data with embedded correlations
    When 10 evolution cycles are executed with seed 42
    Then fitness improvement is at least 15 percent
    And ablation comparison is statistically significant

  Scenario: C3 — Memory persists findings across restarts
    Given behavioral session data with embedded correlations
    And a session memory manager with temporary storage
    When findings are stored from a discovery cycle
    And the memory manager is restarted from the same storage
    Then at least 90 percent of findings are retrievable

  Scenario: C4 — Complete provenance chains for all findings
    Given behavioral session data with embedded correlations
    When a full scientific loop cycle is executed with provenance tracking
    Then all pipeline steps have provenance entries
    And each provenance entry has a valid node_id and description

  Scenario: C5 — Reproducible results with same seed
    Given behavioral session data with embedded correlations
    When the pipeline is executed twice with seed 42
    Then both runs produce identical cycle results
