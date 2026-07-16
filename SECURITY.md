# Security Policy

LinkCutter handles authentication, session cookies, and redirect targets. Treat security reports with care.

## Supported Versions

The repository does not publish a formal support matrix yet. Review and patch the current `main` branch first.

## How To Report A Vulnerability

Do not post exploit details in a public issue.

Use a private channel first:

1. GitHub Security Advisories, if private reporting is enabled for this repository
2. a direct maintainer contact path on GitHub, if the repository does not expose private reporting

Include:

- affected commit or branch
- setup details
- reproduction steps
- impact
- any proof-of-concept material you used

## Current Security-Relevant Defaults

- production must replace `AUTH_SECRET_KEY`
- production must use secure refresh cookies
- development may return verification tokens, password reset tokens, and 2FA codes in API responses
- the API rejects credentials in URLs and non-global targets such as `localhost` and private IP ranges
- refresh tokens rotate and the backend stores only their hashes

## Response Expectations

This repository does not define SLA terms in versioned docs. Share enough detail for maintainers to reproduce the issue and verify a fix.
