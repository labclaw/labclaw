"""Hardware safety — command validation, emergency stop, rate limiting.

All hardware commands pass through this layer:
  - Pydantic schema validation (is this command physically valid?)
  - Permission check (is this member certified to control this device?)
  - Rate limiting (prevent rapid-fire commands)
  - Dry-run mode (digital staff can propose without executing)
  - Emergency stop (any member can trigger, all devices halt)
"""
