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

  Scenario: POST invalid JSON to device endpoint returns 422
    When I POST "/api/devices/" with invalid JSON body
    Then the response status is 422

  Scenario: PATCH device with invalid status returns 422
    When I POST "/api/devices/" with device name "patch-test" type "sensor"
    Then the response status is 201
    And I store the device_id
    When I PATCH the stored device status to "not_a_real_status"
    Then the response status is 422

  Scenario: DELETE nonexistent device returns 404
    When I DELETE "/api/devices/does-not-exist"
    Then the response status is 404

  Scenario: API metrics endpoint returns data
    When I GET "/api/metrics"
    Then the response status is 200
    And the metrics response contains "labclaw_uptime_seconds"

  Scenario: API plugins list endpoint returns a list
    When I GET "/api/plugins/"
    Then the response status is 200
    And the response is a list

  Scenario: API plugins by type endpoint returns a list
    When I GET "/api/plugins/by-type/device"
    Then the response status is 200
    And the response is a list

  Scenario: API agents tools endpoint returns available tools
    When I GET "/api/agents/tools"
    Then the response status is 200
    And the response is a list

  Scenario: API orchestrator history is empty at start
    When I GET "/api/orchestrator/history"
    Then the response status is 200
    And the response is a list

  Scenario: Search memory with empty query returns empty list
    When I GET "/api/memory/search/query?q="
    Then the response status is 200
    And the response is a list

  Scenario: Mining with empty data returns patterns list
    When I POST "/api/discovery/mine" with empty data
    Then the response status is 200
    And the response contains "patterns"

  Scenario: Evolution history filtered by target
    When I GET "/api/evolution/history?target=analysis_params"
    Then the response status is 200
    And the response is a list

  Scenario: Evolution start cycle
    When I POST "/api/evolution/cycle" for target "analysis_params"
    Then the response status is 201

  Scenario: Discovery hypothesize endpoint accepts patterns
    When I POST "/api/discovery/hypothesize" with empty patterns
    Then the hypothesize response is acceptable
