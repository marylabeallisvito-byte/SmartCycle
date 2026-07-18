# Security Policy

## Reporting a Vulnerability

SmartCycle handles financial data and AI-generated investment communications. Security is critical to our mission.

**Please do NOT report security vulnerabilities through public GitHub Issues.**

Instead, report them via email to the project maintainers. We will respond within 48 hours with:

- Confirmation of receipt
- An initial assessment of severity
- A timeline for resolution

## Scope

Issues we consider in-scope for security reporting:

| Area | Examples |
|------|----------|
| **API Keys & Secrets** | Hardcoded credentials, leaked tokens, insecure env handling |
| **LLM Prompt Injection** | Bypass of compliance guardrails via crafted user input |
| **Authentication** | JWT forgery, session hijacking, privilege escalation |
| **Data Exposure** | Unintended disclosure of client profiles, portfolio data, or AI outputs |
| **Dependency Vulnerabilities** | Known CVEs in pinned dependencies |

## Best Practices for Contributors

- **Never commit `.env` files** — They are gitignored. Use `.env.example` as a template.
- **Never hardcode API keys** — Always read from environment variables.
- **Validate all user input** — Especially queries that reach the LLM or compliance engine.
- **Keep dependencies updated** — We use Renovate/Dependabot for automated updates.

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main` (latest) | ✅ Active |
| Release tags | ✅ Supported |

## Disclosure Policy

We follow responsible disclosure:

1. Reporter submits vulnerability privately
2. Maintainers acknowledge within 48 hours
3. Fix is developed and tested
4. Security advisory is published alongside the fix
5. Reporter is credited (unless they opt out)
