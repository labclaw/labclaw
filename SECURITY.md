# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.0.x   | :white_check_mark: |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Please report security issues via email to: **security@shenlab.org**

Include:

- Description of the vulnerability
- Steps to reproduce
- Affected component (API, hardware layer, memory, etc.)
- Potential impact assessment

## Response Timeline

| Stage              | Target            |
|--------------------|-------------------|
| Acknowledgment     | 48 hours          |
| Initial assessment | 5 business days   |
| Fix or mitigation  | 30 days           |
| Public disclosure  | After fix release |

## Scope

### In scope

- API authentication and authorization bypass
- Injection vulnerabilities (SQL, command, path traversal)
- Hardware command safety bypass (sending unapproved commands to devices)
- Memory/audit log tampering
- Credential or API key exposure
- Privilege escalation in governance engine
- Plugin sandbox escape

### Out of scope

- Denial of service against local-only services
- Bugs in third-party dependencies (report upstream)
- Social engineering

## Lab Safety Considerations

LabClaw controls physical laboratory hardware. Security vulnerabilities that could result in:

- **Uncontrolled device activation** (lasers, motors, high-voltage equipment)
- **Safety interlock bypass**
- **Calibration data corruption**
- **Unauthorized experiment execution**

are treated as **critical severity** regardless of software impact assessment.

All hardware write commands pass through the governance engine and require appropriate role-based approval. The `HardwareSafetyGuard` validates device state before command execution.

## Secret Rotation

- API tokens and deploy SSH keys: rotate every 90 days.
- Emergency rotation: within 24 hours of suspected compromise.
- Rotation process:
  - Generate new credential and store in secret manager.
  - Deploy with both old+new credentials accepted during a short overlap window.
  - Remove old credential and verify health checks + audit logs.
- Never log secret values or full token identifiers.
