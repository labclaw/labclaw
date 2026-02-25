Feature: Knowledge Graph (Tier B)
  The system stores and retrieves graph nodes and edges
  in an in-memory temporal knowledge graph.

  Background:
    Given the knowledge graph backend is initialized

  # -----------------------------------------------------------------------
  # Node CRUD
  # -----------------------------------------------------------------------

  Scenario: Add and retrieve a graph node
    When I add a person node with name "Dr. Smith"
    Then the knowledge graph contains 1 node
    And I can retrieve the node by its ID

  Scenario: Get nonexistent node raises KeyError
    When I look up node id "does-not-exist-at-all"
    Then a KeyError is raised for node lookup

  Scenario: Node has a created_at timestamp
    When I add a person node with name "Timestamped Person"
    Then the added node has a created_at timestamp

  Scenario: Duplicate node ID raises error
    Given a person node "dup-1" exists
    Then adding another node with ID "dup-1" raises ValueError

  Scenario: List all nodes in the graph
    Given 3 person nodes exist
    And 2 project nodes exist
    When I list all nodes
    Then I receive a list of 5 nodes

  Scenario: Graph stats reflect node and edge counts
    Given 2 person nodes exist
    And a person node "stats-pi" exists
    And a project node "stats-proj" exists
    And an edge from "stats-pi" to "stats-proj" with relation "leads" exists
    Then the graph node count is 4
    And the graph edge count is 1

  # -----------------------------------------------------------------------
  # Query
  # -----------------------------------------------------------------------

  Scenario: Query nodes by type
    Given 3 person nodes exist
    And 2 project nodes exist
    When I query nodes with type "person"
    Then I receive 3 nodes

  Scenario: Query by type with no matches returns empty list
    Given 2 person nodes exist
    When I query nodes with type "recording"
    Then I receive 0 nodes

  # -----------------------------------------------------------------------
  # Search
  # -----------------------------------------------------------------------

  Scenario: Search nodes by text
    Given a person node with name "Dr. Alice Zhang" exists
    And a person node with name "Dr. Bob Johnson" exists
    When I search the knowledge graph for "Alice"
    Then search results contain a node with name "Dr. Alice Zhang"

  Scenario: Search with no results returns empty list
    Given a person node with name "Dr. Carol White" exists
    When I search the knowledge graph for "xyzzy-no-match-term"
    Then the search result list is empty

  # -----------------------------------------------------------------------
  # Edge CRUD
  # -----------------------------------------------------------------------

  Scenario: Add an edge between two nodes
    Given a person node "researcher-1" exists
    And a project node "project-alpha" exists
    When I add an edge from "researcher-1" to "project-alpha" with relation "leads"
    Then the knowledge graph contains 1 edge
    And the edge has relation "leads"

  Scenario: Edge has properties
    Given a person node "prop-person" exists
    And a project node "prop-project" exists
    When I add an edge from "prop-person" to "prop-project" with relation "contributes" and property "weight" equal to "0.9"
    Then the edge property "weight" equals "0.9"

  Scenario: Multiple edges between the same two nodes
    Given a person node "multi-src" exists
    And a project node "multi-tgt" exists
    When I add an edge from "multi-src" to "multi-tgt" with relation "leads"
    And I add another edge from "multi-src" to "multi-tgt" with relation "reviews"
    Then there are 2 edges between "multi-src" and "multi-tgt"

  Scenario: Add edge with nonexistent source raises KeyError
    Given a project node "orphan-project" exists
    When I try to add an edge from "ghost-node" to "orphan-project" with relation "member_of"
    Then a KeyError is raised for edge creation

  Scenario: Add edge with nonexistent target raises KeyError
    Given a person node "real-person" exists
    When I try to add an edge from "real-person" to "ghost-target" with relation "member_of"
    Then a KeyError is raised for edge creation

  Scenario: Remove an edge by ID
    Given a person node "edge-src" exists
    And a project node "edge-tgt" exists
    And an edge from "edge-src" to "edge-tgt" with relation "owns" exists
    When I remove the last added edge
    Then the knowledge graph contains 0 edges

  Scenario: Remove nonexistent edge raises KeyError
    When I try to remove edge id "nonexistent-edge-id-abc"
    Then a KeyError is raised for edge removal

  # -----------------------------------------------------------------------
  # Neighbors & edges query
  # -----------------------------------------------------------------------

  Scenario: Get neighbors of a node
    Given a person node "pi-1" exists
    And a project node "proj-1" exists
    And an edge from "pi-1" to "proj-1" with relation "leads" exists
    When I get neighbors of "pi-1"
    Then I receive 1 neighbor
    And the neighbor is "proj-1"

  Scenario: Get outgoing neighbors only
    Given a person node "out-src" exists
    And a project node "out-tgt" exists
    And an edge from "out-src" to "out-tgt" with relation "owns" exists
    When I get outgoing neighbors of "out-tgt"
    Then I receive 0 neighbors

  Scenario: Get all edges for a node
    Given a person node "edge-node" exists
    And a project node "edge-proj-a" exists
    And a project node "edge-proj-b" exists
    And an edge from "edge-node" to "edge-proj-a" with relation "leads" exists
    And an edge from "edge-node" to "edge-proj-b" with relation "reviews" exists
    When I get all edges between "edge-node" and "edge-proj-a"
    Then I receive 1 edge between them

  # -----------------------------------------------------------------------
  # Node removal
  # -----------------------------------------------------------------------

  Scenario: Remove a node removes connected edges
    Given a person node "temp-person" exists
    And a project node "temp-project" exists
    And an edge from "temp-person" to "temp-project" with relation "works_on" exists
    When I remove node "temp-person"
    Then the knowledge graph contains 0 edges

  Scenario: Remove nonexistent node raises KeyError
    When I try to remove node "ghost-node-xyz"
    Then a KeyError is raised for node removal
