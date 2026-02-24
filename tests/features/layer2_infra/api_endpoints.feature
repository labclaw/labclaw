Feature: REST API Endpoints
  The system exposes a REST API for interacting with all layers.

  Background:
    Given the API test client is initialized

  Scenario: Health check
    When I GET "/api/health"
    Then the response status is 200
    And the response contains "status"

  Scenario: System status
    When I GET "/api/status"
    Then the response status is 200
    And the response contains "registered_events"

  Scenario: Register and list devices
    When I POST "/api/devices/" with device name "cam-001" type "camera"
    Then the response status is 201
    When I GET "/api/devices/"
    Then the response status is 200
    And the response contains 1 device

  Scenario: Get device by id
    When I POST "/api/devices/" with device name "mic-002" type "microphone"
    Then the response status is 201
    And I store the device_id
    When I GET the stored device
    Then the response status is 200
    And the response contains "name" with value "mic-002"

  Scenario: Update device status
    When I POST "/api/devices/" with device name "scope-003" type "microscope"
    Then the response status is 201
    And I store the device_id
    When I PATCH the stored device status to "online"
    Then the response status is 200

  Scenario: Delete a device
    When I POST "/api/devices/" with device name "tmp-dev" type "temp"
    Then the response status is 201
    And I store the device_id
    When I DELETE the stored device
    Then the response status is 200

  Scenario: Get nonexistent device returns 404
    When I GET "/api/devices/nonexistent-id"
    Then the response status is 404

  Scenario: Start and end a session
    When I POST "/api/sessions/" with operator "alice"
    Then the response status is 201
    And the response contains a session_id
    When I POST end session for the stored session_id
    Then the response status is 200

  Scenario: List sessions
    When I POST "/api/sessions/" with operator "bob"
    Then the response status is 201
    When I GET "/api/sessions/"
    Then the response status is 200

  Scenario: Get nonexistent session returns 404
    When I GET "/api/sessions/nonexistent-id"
    Then the response status is 404

  Scenario: List registered events
    When I GET "/api/events/"
    Then the response status is 200
    And the response is a list

  Scenario: Search memory returns results
    When I GET "/api/memory/search/query?q=test"
    Then the response status is 200

  Scenario: Run mining pipeline
    When I POST "/api/discovery/mine" with sample data
    Then the response status is 200
    And the response contains "patterns"

  Scenario: Measure fitness
    When I POST "/api/evolution/fitness" for target "analysis_params"
    Then the response status is 200
    And the response contains "target"

  Scenario: Evolution history starts empty
    When I GET "/api/evolution/history"
    Then the response status is 200
    And the response is a list
