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
