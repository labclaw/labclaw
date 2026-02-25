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

  Scenario: Clustering with k=1 returns single cluster
    Given experimental data with 3 distinct clusters of 10 points each
    When I run clustering with k=1
    Then 1 clusters are found

  Scenario: Empty data returns empty cluster result
    Given empty clustering data
    When I run clustering with k=3
    Then 0 clusters are found

  Scenario: PCA n_components clamped to n_features
    Given experimental data with 2 numeric columns and 10 rows
    When I reduce dimensionality to 5 components
    Then each projected point has at most 2 dimensions

  Scenario: PCA on 1D data returns single component
    Given experimental data with 1 numeric column and 10 rows
    When I reduce dimensionality to 2 components
    Then each projected point has 1 dimensions

  Scenario: Cluster pattern evidence has correct fields
    Given experimental data with 2 distinct clusters of 8 points each
    When I discover cluster patterns with k=2
    Then the cluster pattern evidence has method field
    And the cluster pattern evidence has inertia field
    And the cluster pattern evidence has cluster_sizes field

  Scenario: Discovery on data with all identical values still runs
    Given experimental data with 10 identical rows
    When I run clustering with k=2
    Then the clustering runs without error

  Scenario: Pure-python fallback clustering produces labels
    Given experimental data with 2 distinct clusters of 5 points each
    When I run pure python kmeans with k=2
    Then the pure python result has 2 cluster labels
