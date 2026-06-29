# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.x     | ✅ Yes    |
| 1.x     | ❌ No     |

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Email: ansiee3103@email.com

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours.

## Security Features

- JWT authentication with expiry
- bcrypt password hashing
- Rate limiting on all endpoints
- Pre-flight secrets scanner
- Security headers (XSS, CSRF)
- RBAC (Role-Based Access Control)
- Audit logging
- HTTPS enforced    