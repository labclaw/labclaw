Feature: Memory Layer Hardening
  Entity ID validation prevents path traversal; session memory manager
  closes Tier B resources cleanly on shutdown.

  # -----------------------------------------------------------------------
  # entity_id validation — path traversal prevention
  # -----------------------------------------------------------------------

  Scenario: Valid entity_id is accepted
    Given the memory tier A backend is initialized
    When I attempt to create a SOUL for entity "valid-lab-01"
    Then no error is raised

  Scenario: Entity ID with path traversal is rejected
    Given the memory tier A backend is initialized
    When I attempt to create a SOUL for entity "../evil"
    Then a ValueError is raised with "entity_id must match"

  Scenario: Entity ID with double-dot segment is rejected
    Given the memory tier A backend is initialized
    When I attempt to create a SOUL for entity "lab..evil"
    Then a ValueError is raised with "entity_id must match"

  Scenario: Empty entity ID is rejected
    Given the memory tier A backend is initialized
    When I attempt to create a SOUL with an empty entity id
    Then a ValueError is raised with "non-empty"

  Scenario: Entity ID starting with dot is rejected
    Given the memory tier A backend is initialized
    When I attempt to create a SOUL for entity ".hidden"
    Then a ValueError is raised with "entity_id must match"

  # -----------------------------------------------------------------------
  # SessionMemoryManager.close()
  # -----------------------------------------------------------------------

  Scenario: Session memory manager closes without Tier B backend
    Given a session memory manager with no Tier B backend
    When I close the session memory manager
    Then close completes without error

  Scenario: Session memory manager closes with Tier B backend
    Given a session memory manager with a mock Tier B backend
    When I close the session memory manager
    Then the Tier B backend close method was called
