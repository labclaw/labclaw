Feature: Predictive Modeling (PREDICT step)
  The system trains predictive models on experimental data,
  provides feature importance rankings and uncertainty estimates.

  Background:
    Given the predictive model is initialized

  Scenario: Train a linear model on correlated data
    Given training data with target "y" and features "x1" and "x2" over 30 rows
    When I train the model with target "y" and method "linear"
    Then the model is trained successfully
    And the R-squared is greater than 0.5
    And feature importances are ranked
    And an event "discovery.model.trained" is emitted

  Scenario: Predict with uncertainty estimates
    Given training data with target "y" and features "x1" and "x2" over 30 rows
    And the model is trained with target "y"
    When I predict on new data with 5 rows
    Then 5 predictions are returned
    And each prediction has lower and upper bounds
    And an event "discovery.model.predicted" is emitted

  Scenario: Training on insufficient data returns zero R-squared
    Given training data with only 2 rows
    When I train the model with target "y" and method "linear"
    Then the R-squared is 0.0

  Scenario: Train a random forest model
    Given training data with target "y" and features "x1" and "x2" over 30 rows
    When I train the model with target "y" and method "random_forest"
    Then the model is trained successfully
    And the R-squared is greater than 0.5
    And feature importances are ranked

  Scenario: Predict without training first raises error
    When I predict without training
    Then a RuntimeError is raised

  Scenario: Feature importances have correct column names
    Given training data with target "y" and features "x1" and "x2" over 30 rows
    When I train the model with target "y" and method "linear"
    Then feature importance column names match the feature columns

  Scenario: Bootstrap confidence intervals contain the prediction
    Given training data with target "y" and features "x1" and "x2" over 30 rows
    And the model is trained with target "y"
    When I predict on new data with 3 rows
    Then each prediction has a lower bound less than or equal to the upper bound

  Scenario: Train on data with a constant feature has zero variance feature
    Given training data with a constant feature "x_const" and varying "x1" over 20 rows
    When I train the model with target "y" and method "linear"
    Then the model is trained successfully
    And the R-squared is greater than 0.0

  Scenario: Pure-python fallback produces valid R-squared
    Given training data with target "y" and features "x1" and "x2" over 20 rows
    When I train with pure python fallback
    Then the pure python R-squared is non-negative
