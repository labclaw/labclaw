Feature: Background Task Queue (L2)
  The task queue provides persistent async task execution with
  priority ordering, retry logic, and event-driven state transitions.

  Scenario: Enqueue and dequeue a task
    Given an initialized task queue
    When I enqueue a task named "analyze-data"
    Then I can dequeue the task named "analyze-data"

  Scenario: Dequeue from empty queue returns nothing
    Given an initialized task queue
    When I dequeue from the empty queue
    Then no task is returned

  Scenario: Priority ordering
    Given an initialized task queue
    When I enqueue tasks with priorities 1, 10, and 5
    Then the first dequeued task has priority 10

  Scenario: Task status transitions to running
    Given an initialized task queue
    And a task named "status-test" is enqueued
    When I update the task status to "running"
    Then the task status is "running"
    And the task has a started_at timestamp

  Scenario: Task status transitions to completed
    Given an initialized task queue
    And a task named "complete-test" is enqueued
    When I complete the task with result "done"
    Then the task status is "completed"
    And the task has a completed_at timestamp

  Scenario: Task failure increments retry count
    Given an initialized task queue
    And a task named "fail-test" is enqueued
    When I fail the task with error "bad input"
    Then the task status is "failed"
    And the task retry count is 1

  Scenario: Cancel a pending task
    Given an initialized task queue
    And a task named "cancel-test" is enqueued
    When I cancel the task
    Then the task status is "cancelled"

  Scenario: Cannot cancel a completed task
    Given an initialized task queue
    And a completed task named "done-task"
    When I try to cancel the completed task
    Then a ValueError is raised for cancel

  Scenario: Enqueue emits event
    Given an initialized task queue with event capture
    When I enqueue a task named "event-task"
    Then the event "infra.task_queue.enqueued" was emitted

  Scenario: List tasks filtered by status
    Given an initialized task queue
    And tasks "a" and "b" are enqueued
    And task "a" is set to running
    When I list pending tasks
    Then only task "b" is in the pending list
