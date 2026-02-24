Feature: Markdown Memory (Tier A)
  The system stores and retrieves SOUL.md and MEMORY.md files
  as the source-of-truth for all entity identities and histories.

  Background:
    Given the memory tier A backend is initialized

  Scenario: Create and read an entity's SOUL.md
    When I create a SOUL for entity "shen-lab" with name "Shen Lab"
    And I request the SOUL for entity "shen-lab"
    Then I receive a MarkdownDoc with frontmatter containing "name"
    And the frontmatter "name" is "Shen Lab"
    And the content is valid markdown
    And an event "memory.tier_a.created" is emitted

  Scenario: Append a correction to MEMORY.md
    Given entity "intern-alpha" has a SOUL.md with name "Intern Alpha"
    When I append a memory entry with category "analysis_error" and detail "Used wrong baseline"
    And I append a memory entry with category "protocol" and detail "Updated staining protocol"
    Then the MEMORY.md for "intern-alpha" has 2 entries
    And an event "memory.tier_a.updated" is emitted

  Scenario: Read SOUL for nonexistent entity raises error
    When I request the SOUL for entity "nonexistent"
    Then a FileNotFoundError is raised

  Scenario: Memory search returns ranked results
    Given entity "alice" has a SOUL.md with name "Alice"
    And entity "alice" has memory entries about "baseline calibration procedure"
    And entity "bob" has a SOUL.md with name "Bob"
    And entity "bob" has memory entries about "electrode impedance"
    When I search memory for "baseline calibration"
    Then results contain entity "alice"
    And results are ranked by relevance score
