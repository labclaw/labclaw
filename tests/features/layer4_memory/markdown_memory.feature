Feature: Markdown Memory (Tier A)
  The system stores and retrieves SOUL.md and MEMORY.md files
  as the source-of-truth for all entity identities and histories.

  Background:
    Given the memory tier A backend is initialized

  # -----------------------------------------------------------------------
  # SOUL.md create / read
  # -----------------------------------------------------------------------

  Scenario: Create and read an entity's SOUL.md
    When I create a SOUL for entity "labclaw" with name "LabClaw"
    And I request the SOUL for entity "labclaw"
    Then I receive a MarkdownDoc with frontmatter containing "name"
    And the frontmatter "name" is "LabClaw"
    And the content is valid markdown
    And an event "memory.tier_a.created" is emitted

  Scenario: Create SOUL with rich metadata
    When I create a SOUL for entity "pi-wang" with role "pi" and status "active" and capabilities "imaging,ephys"
    And I request the SOUL for entity "pi-wang"
    Then the frontmatter "role" is "pi"
    And the frontmatter "status" is "active"

  Scenario: Read SOUL for nonexistent entity raises error
    When I request the SOUL for entity "nonexistent"
    Then a FileNotFoundError is raised

  # -----------------------------------------------------------------------
  # SOUL.md update
  # -----------------------------------------------------------------------

  Scenario: Update an existing SOUL.md
    Given entity "update-lab" has a SOUL.md with name "Update Lab"
    When I update the SOUL for entity "update-lab" with name "Updated Lab Name"
    And I request the SOUL for entity "update-lab"
    Then the frontmatter "name" is "Updated Lab Name"
    And an event "memory.tier_a.updated" is emitted

  # -----------------------------------------------------------------------
  # List entities
  # -----------------------------------------------------------------------

  Scenario: List all entities in the backend
    Given entity "lab-a" has a SOUL.md with name "Lab A"
    And entity "lab-b" has a SOUL.md with name "Lab B"
    And entity "lab-c" has a SOUL.md with name "Lab C"
    When I list all entities
    Then the entity list contains "lab-a"
    And the entity list contains "lab-b"
    And the entity list contains "lab-c"

  # -----------------------------------------------------------------------
  # MEMORY.md append / read
  # -----------------------------------------------------------------------

  Scenario: Append a correction to MEMORY.md
    Given entity "intern-alpha" has a SOUL.md with name "Intern Alpha"
    When I append a memory entry with category "analysis_error" and detail "Used wrong baseline"
    And I append a memory entry with category "protocol" and detail "Updated staining protocol"
    Then the MEMORY.md for "intern-alpha" has 2 entries
    And an event "memory.tier_a.updated" is emitted

  Scenario: Memory entry has a timestamp
    Given entity "ts-entity" has a SOUL.md with name "Timestamp Entity"
    When I append a memory entry with category "note" and detail "Timestamped observation"
    Then the MEMORY.md for "ts-entity" has 1 entries
    And the memory entry contains a timestamp header

  Scenario: Get memory for entity with no MEMORY.md raises error
    Given entity "empty-entity" has a SOUL.md with name "Empty Entity"
    When I request the memory for entity "empty-entity"
    Then a FileNotFoundError is raised for memory read

  Scenario: Memory entries are in chronological order
    Given entity "ordered-entity" has a SOUL.md with name "Ordered Entity"
    When I append a memory entry with category "early" and detail "First event observation"
    And I append a memory entry with category "late" and detail "Second event observation"
    Then the MEMORY.md for "ordered-entity" has 2 entries
    And the memory entries appear in chronological order

  Scenario: Multiple entities with different memory categories
    Given entity "alice" has a SOUL.md with name "Alice"
    And entity "bob" has a SOUL.md with name "Bob"
    When I append a memory entry for "alice" with category "experiment" and detail "Ran imaging session"
    And I append a memory entry for "bob" with category "protocol" and detail "Updated buffer recipe"
    Then the MEMORY.md for "alice" has 1 entries
    And the MEMORY.md for "bob" has 1 entries

  # -----------------------------------------------------------------------
  # Search
  # -----------------------------------------------------------------------

  Scenario: Memory search returns ranked results
    Given entity "alice" has a SOUL.md with name "Alice"
    And entity "alice" has memory entries about "baseline calibration procedure"
    And entity "bob" has a SOUL.md with name "Bob"
    And entity "bob" has memory entries about "electrode impedance"
    When I search memory for "baseline calibration"
    Then results contain entity "alice"
    And results are ranked by relevance score

  Scenario: Search with multiple keyword matches scores higher
    Given entity "high-score" has a SOUL.md with name "High Score Entity"
    And entity "high-score" has memory entries about "calcium imaging calcium signals calcium transients"
    And entity "low-score" has a SOUL.md with name "Low Score Entity"
    And entity "low-score" has memory entries about "calcium one mention only"
    When I search memory for "calcium"
    Then results contain entity "high-score"
    And results are ranked by relevance score

  Scenario: Search with no results returns empty list
    Given entity "isolated" has a SOUL.md with name "Isolated Entity"
    When I search memory for "xyzzy-impossible-search-term"
    Then memory search results are empty

  Scenario: Search finds content in both SOUL.md and MEMORY.md
    Given entity "dual-match" has a SOUL.md with name "Dual Match Entity"
    And entity "dual-match" has memory entries about "unique-search-token-gamma"
    When I search memory for "unique-search-token-gamma"
    Then results contain entity "dual-match"
