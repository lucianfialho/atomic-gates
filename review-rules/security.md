# Security Review Rules

Loaded when security review is requested or when sensitive files are changed.

## Input Validation
- User input validated and sanitized before use
- File uploads validated (type, size, content)
- URL parameters and query strings validated

## Injection Prevention
- SQL queries parameterized (no string concatenation)
- No `dangerouslySetInnerHTML` without sanitization
- No shell command construction from user input
- No file path construction from user input without validation

## Secrets
- No hardcoded API keys, tokens, or passwords
- Secrets read from environment variables
- `.env` files in `.gitignore`
- Error messages don't leak internal details

## Auth
- Authentication checks on all protected routes
- CSRF protection on state-changing operations
- Rate limiting on public API endpoints
- No sensitive data in client-side code or localStorage
- CORS headers properly configured

## Dependencies
- New dependencies audited for known vulnerabilities
- No unnecessary permissions requested
- Dependencies pinned to specific versions
