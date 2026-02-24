Feature: Unsupervised Discovery (ASK — hidden structure)
  The system discovers hidden structure in experimental data through
  clustering and dimensionality reduction, without pre-defined labels.

  Background:
    Given the cluster discovery engine is initialized

  Scenario: K-means clustering discovers subpopulations
    Given experimental data with 3 distinct clusters of 10 points each
    When I run clustering with k=3
    Then 3 clusters are found
    And each cluster has at least 5 members

  Scenario: Discover patterns produces PatternRecords
    Given experimental data with 3 distinct clusters of 10 points each
    When I discover cluster patterns with k=3
    Then at least 1 cluster pattern is returned
    And the pattern has type "cluster"
    And the pattern evidence contains n_clusters
    And an event "discovery.cluster.found" is emitted

  Scenario: Clustering clamps k to n when data has fewer rows than requested clusters
    Given experimental data with only 2 rows for clustering
    When I run clustering with k=3
    Then 2 clusters are found

  Scenario: PCA reduces dimensionality
    Given experimental data with 5 numeric columns and 20 rows
    When I reduce dimensionality to 2 components
    Then the reduction result has 20 projected points
    And each projected point has 2 dimensions
    And an event "discovery.reduction.completed" is emitted
