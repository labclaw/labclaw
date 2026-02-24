Feature: Knowledge Graph (Tier B)
  The system stores and retrieves graph nodes and edges
  in an in-memory temporal knowledge graph.

  Background:
    Given the knowledge graph backend is initialized

  Scenario: Add and retrieve a graph node
    When I add a person node with name "Dr. Smith"
    Then the knowledge graph contains 1 node
    And I can retrieve the node by its ID

  Scenario: Add an edge between two nodes
    Given a person node "researcher-1" exists
    And a project node "project-alpha" exists
    When I add an edge from "researcher-1" to "project-alpha" with relation "leads"
    Then the knowledge graph contains 1 edge
    And the edge has relation "leads"

  Scenario: Query nodes by type
    Given 3 person nodes exist
    And 2 project nodes exist
    When I query nodes with type "person"
    Then I receive 3 nodes

  Scenario: Get neighbors of a node
    Given a person node "pi-1" exists
    And a project node "proj-1" exists
    And an edge from "pi-1" to "proj-1" with relation "leads" exists
    When I get neighbors of "pi-1"
    Then I receive 1 neighbor
    And the neighbor is "proj-1"

  Scenario: Search nodes by text
    Given a person node with name "Dr. Alice Zhang" exists
    And a person node with name "Dr. Bob Johnson" exists
    When I search the knowledge graph for "Alice"
    Then search results contain a node with name "Dr. Alice Zhang"

  Scenario: Remove a node removes connected edges
    Given a person node "temp-person" exists
    And a project node "temp-project" exists
    And an edge from "temp-person" to "temp-project" with relation "works_on" exists
    When I remove node "temp-person"
    Then the knowledge graph contains 0 edges

  Scenario: Duplicate node ID raises error
    Given a person node "dup-1" exists
    Then adding another node with ID "dup-1" raises ValueError
