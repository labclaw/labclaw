Feature: SQLite Tier B Backend (persistent knowledge graph)
  The SQLiteTierBBackend provides the same graph API as the in-memory
  backend but persists data to an SQLite file.

  Background:
    Given the SQLite Tier B backend is initialized

  # -----------------------------------------------------------------------
  # Initialization
  # -----------------------------------------------------------------------

  Scenario: Initialize creates an empty database
    Then the SQLite backend has 0 nodes
    And the SQLite backend has 0 edges

  # -----------------------------------------------------------------------
  # Node CRUD
  # -----------------------------------------------------------------------

  Scenario: Add and retrieve a node from SQLite
    When I add a person node "sqlite-pi" to the SQLite backend
    Then I can retrieve node "sqlite-pi" from the SQLite backend
    And the SQLite backend has 1 nodes

  Scenario: Add duplicate node ID raises ValueError in SQLite
    When I add a person node "sqlite-dup" to the SQLite backend
    Then adding "sqlite-dup" again to the SQLite backend raises ValueError

  Scenario: Get nonexistent node from SQLite raises KeyError
    When I look up "ghost-sqlite-node" in the SQLite backend
    Then a KeyError is raised for SQLite node lookup

  Scenario: Remove a node from SQLite
    When I add a person node "sqlite-rm" to the SQLite backend
    And I remove node "sqlite-rm" from the SQLite backend
    Then the SQLite backend has 0 nodes

  Scenario: Remove nonexistent node from SQLite raises KeyError
    When I try to remove "ghost-sqlite-rm" from the SQLite backend
    Then a KeyError is raised for SQLite node removal

  Scenario: Update a node in SQLite
    When I add a person node "sqlite-update" to the SQLite backend
    And I update node "sqlite-update" name to "Updated Name" in the SQLite backend
    Then retrieving "sqlite-update" from SQLite has name "Updated Name"

  # -----------------------------------------------------------------------
  # Edge CRUD
  # -----------------------------------------------------------------------

  Scenario: Add and count an edge in SQLite
    Given SQLite node "sq-src" exists
    And SQLite node "sq-tgt" exists
    When I add an edge from "sq-src" to "sq-tgt" with relation "sq-rel" in SQLite
    Then the SQLite backend has 1 edges

  Scenario: Remove an edge from SQLite
    Given SQLite node "sq-e-src" exists
    And SQLite node "sq-e-tgt" exists
    And a SQLite edge from "sq-e-src" to "sq-e-tgt" with relation "sq-e-rel" exists
    When I remove the SQLite edge
    Then the SQLite backend has 0 edges

  Scenario: Remove nonexistent edge from SQLite raises KeyError
    When I try to remove SQLite edge "nonexistent-sqlite-edge-id"
    Then a KeyError is raised for SQLite edge removal

  # -----------------------------------------------------------------------
  # Query & search
  # -----------------------------------------------------------------------

  Scenario: Query nodes by type in SQLite
    When I add a person node "sq-person-a" to the SQLite backend
    And I add a person node "sq-person-b" to the SQLite backend
    And I query SQLite nodes by type "person"
    Then I receive 2 SQLite nodes

  Scenario: Text search in SQLite returns matching node
    When I add a protocol node "sq-search-proto" with name "Calcium Imaging Protocol" to SQLite
    And I search the SQLite backend for "Calcium"
    Then the SQLite search results contain a node named "Calcium Imaging Protocol"

  # -----------------------------------------------------------------------
  # Persistence
  # -----------------------------------------------------------------------

  Scenario: Database persists across backend instances
    When I add a person node "persist-node" to the SQLite backend
    And I close and reopen the SQLite backend at the same path
    Then I can retrieve node "persist-node" from the SQLite backend
