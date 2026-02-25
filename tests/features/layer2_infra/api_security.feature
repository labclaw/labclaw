Feature: API Security
  The REST API enforces authentication, CORS, rate limiting, and exception
  sanitization to prevent unauthorized access and information leakage.

  Background:
    Given the security test client is initialized

  # ---------------------------------------------------------------------------
  # Auth-exempt paths
  # ---------------------------------------------------------------------------

  Scenario: Health endpoint is accessible without authentication
    Given authentication is required
    When I GET the health endpoint without credentials
    Then the response status is 200

  Scenario: Metrics endpoint is accessible without authentication
    Given authentication is required
    When I GET the metrics endpoint without credentials
    Then the response status is 200

  # ---------------------------------------------------------------------------
  # Bearer token authentication — happy path
  # ---------------------------------------------------------------------------

  Scenario: Bearer token grants access to protected endpoint
    Given authentication is required with token "test-secret"
    When I GET "/api/events/" with Bearer token "test-secret"
    Then the response status is 200

  Scenario: X-API-Key header grants access to protected endpoint
    Given authentication is required with token "test-secret"
    When I GET "/api/events/" with X-API-Key header "test-secret"
    Then the response status is 200

  # ---------------------------------------------------------------------------
  # Authentication failure paths
  # ---------------------------------------------------------------------------

  Scenario: Missing credentials return 401
    Given authentication is required with token "test-secret"
    When I GET "/api/events/" without any credentials
    Then the response status is 401

  Scenario: Wrong Bearer token returns 401
    Given authentication is required with token "test-secret"
    When I GET "/api/events/" with Bearer token "wrong-token"
    Then the response status is 401

  Scenario: Auth enabled but no token configured returns 503
    Given authentication is required and no tokens are configured
    When I GET "/api/events/" without any credentials
    Then the response status is 503

  # ---------------------------------------------------------------------------
  # CORS middleware
  # ---------------------------------------------------------------------------

  Scenario: CORS preflight returns correct headers when origins are configured
    Given CORS is configured with origin "http://localhost:3000"
    When I send an OPTIONS preflight request to "/api/devices/" from "http://localhost:3000"
    Then the response status is 200
    And the response includes an Access-Control-Allow-Origin header

  Scenario: CORS headers are absent when no origins are configured
    Given no CORS origins are configured
    When I GET "/api/health" from origin "http://evil.example.com"
    Then the response has no Access-Control-Allow-Origin header

  # ---------------------------------------------------------------------------
  # Rate limiting
  # ---------------------------------------------------------------------------

  Scenario: Requests within the rate limit succeed
    Given rate limiting is enabled with a limit of 3 per minute
    When I make 3 requests to "/api/events/"
    Then all requests succeed with status 200

  Scenario: Exceeding the rate limit returns 429
    Given rate limiting is enabled with a limit of 2 per minute
    When I make 3 requests to "/api/events/"
    Then the third request returns status 429

  Scenario: Rate limit does not apply to auth-exempt paths
    Given rate limiting is enabled with a limit of 1 per minute
    When I make 3 requests to "/api/health"
    Then all requests succeed with status 200

  # ---------------------------------------------------------------------------
  # Exception sanitization
  # ---------------------------------------------------------------------------

  Scenario: Unhandled server exceptions return a generic 500 message
    Given the orchestrator is configured to raise an unexpected error
    When I POST "/api/orchestrator/cycle" with empty data rows
    Then the response status is 500
    And the response detail is "Internal server error"
    And the response detail does not contain internal error information

  # ---------------------------------------------------------------------------
  # Governance integration
  # ---------------------------------------------------------------------------

  Scenario: Digital intern role is denied write access
    Given authentication is required with token "test-secret"
    And governance enforcement is enabled
    And the default role is "digital_intern"
    When I POST "/api/sessions/" with operator "robot" and Bearer token "test-secret"
    Then the response status is 403

  Scenario: Postdoc role is allowed write access via token-role mapping
    Given authentication is required with token "test-secret"
    And governance enforcement is enabled
    And token "test-secret" is mapped to role "postdoc"
    When I POST "/api/sessions/" with operator "robot" and Bearer token "test-secret"
    Then the response status is 201

  Scenario: Client-supplied role header is ignored
    Given authentication is required with token "test-secret"
    And governance enforcement is enabled
    And the default role is "digital_intern"
    When I POST "/api/sessions/" with operator "robot" claiming role "pi" with Bearer token "test-secret"
    Then the response status is 403
