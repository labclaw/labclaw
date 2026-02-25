Feature: Hybrid Memory Search (L4 Search Engine)
  The HybridSearchEngine combines Tier A (markdown) and Tier B (knowledge
  graph) results into a single ranked list.

  Background:
    Given the hybrid search engine is initialized with tier A and tier B

  # -----------------------------------------------------------------------
  # Basic search
  # -----------------------------------------------------------------------

  Scenario: Search across Tier A returns markdown results
    Given a markdown entity "pi-zhang" with SOUL content "Dr. Zhang leads the imaging project"
    When I run a hybrid search for "imaging"
    Then the hybrid results contain source tier "a"

  Scenario: Search across Tier B returns graph node results
    Given a knowledge graph node with name "Fluorescence Microscopy Protocol"
    When I run a hybrid search for "Fluorescence"
    Then the hybrid results contain source tier "b"

  Scenario: Search across both tiers returns combined results
    Given a markdown entity "combo-entity" with SOUL content "unique-combo-token-delta"
    And a knowledge graph node with name "unique-combo-token-delta experiment"
    When I run a hybrid search for "unique-combo-token-delta"
    Then the hybrid results contain source tier "a"
    And the hybrid results contain source tier "b"

  Scenario: Search results are sorted by score descending
    Given a markdown entity "best-match" with SOUL content "calcium calcium calcium imaging calcium"
    And a markdown entity "weak-match" with SOUL content "calcium"
    When I run a hybrid search for "calcium"
    Then hybrid results are ranked by score descending

  Scenario: Search with empty query returns empty results
    Given a markdown entity "some-entity" with SOUL content "some content"
    When I run a hybrid search with an empty query
    Then the hybrid result list is empty

  Scenario: Search respects the result limit
    Given 5 markdown entities with content "limitcheck experiment data"
    When I run a hybrid search for "limitcheck" with limit 3
    Then I receive at most 3 hybrid results

  # -----------------------------------------------------------------------
  # Entity filter
  # -----------------------------------------------------------------------

  Scenario: Search filters by entity ID
    Given a markdown entity "target-entity" with SOUL content "filtertest experiment observation"
    And a markdown entity "other-entity" with SOUL content "filtertest experiment control"
    When I run a hybrid search for "filtertest" filtered by entity "target-entity"
    Then all hybrid results have entity id "target-entity"

  # -----------------------------------------------------------------------
  # Tier-only search
  # -----------------------------------------------------------------------

  Scenario: Search Tier A only skips knowledge graph
    Given a knowledge graph node with name "tier-b-only-result-xyz"
    When I run a hybrid search for "tier-b-only-result-xyz" in tier "a" only
    Then the hybrid result list is empty

  Scenario: Search Tier B only skips markdown
    Given a markdown entity "tier-a-only" with SOUL content "tier-a-only-result-abc"
    When I run a hybrid search for "tier-a-only-result-abc" in tier "b" only
    Then the hybrid result list is empty
