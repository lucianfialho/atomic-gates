---
name: check-security
description: Security-focused review of a PR — injection, XSS, auth, secrets, dependencies
args: pr_number
---

# Security Check

Run a focused security analysis on a PR diff. Checks for OWASP Top 10 vulnerabilities, hardcoded secrets, auth gaps, and dependency risks.

## Usage

```
/check-security          — Check the current PR branch
/check-security 42       — Check PR #42
```

Also works as `@claude check security` in GitHub PR comments.

## Process

### 1. Get the changes

```bash
gh pr view --json number,title,body,files
gh pr diff
```

### 2. Security checklist

Analyze every changed file against these categories:

#### Input Validation
- Are all user inputs validated before use?
- Are inputs sanitized for the context (HTML, SQL, shell, regex)?
- Are file uploads validated (type, size, content)?
- Are URL parameters and query strings validated?
- Are request bodies validated against a schema?

#### Injection
- **SQL**: Are all queries parameterized? No string concatenation for SQL?
- **XSS**: Is output escaped in templates? Any `dangerouslySetInnerHTML`?
- **Command injection**: Are shell commands built from user input?
- **Path traversal**: Are file paths validated? No `../` in user input?
- **SSRF**: Are URLs fetched from user input validated against allowlists?

#### Authentication & Authorization
- Do protected routes check authentication?
- Is authorization checked (not just authentication)?
- Are JWT tokens validated properly (signature, expiration, issuer)?
- Are session tokens regenerated after login?
- Is password handling done with proper hashing (bcrypt, argon2)?

#### Secrets & Configuration
- Are there hardcoded API keys, tokens, or passwords?
- Are secrets read from environment variables, not code?
- Is `.env` in `.gitignore`?
- Are default credentials or admin passwords present?
- Are error messages leaking internal details (stack traces, DB schemas)?

#### Dependencies
- Were new dependencies added? Run `npm audit` / `pnpm audit` if so
- Are dependencies pinned to specific versions?
- Are there known vulnerabilities in new/updated packages?

#### Data Protection
- Is sensitive data encrypted at rest and in transit?
- Are PII fields properly handled (logging, serialization)?
- Is CSRF protection in place for state-changing operations?
- Are rate limits configured on public-facing endpoints?
- Are CORS headers properly configured?

### 3. Output format

```markdown
## Security Review

### Summary
<1-2 sentence overview. Include count of findings by severity.>

### 🔴 Critical
Must fix before merge — exploitable vulnerabilities.

- **`file:line`** — <vulnerability type>
  **Risk**: <what an attacker could do>
  **Fix**: <concrete remediation>

### 🟡 Warning
Should fix — creates risk but not immediately exploitable.

- **`file:line`** — <issue description>
  **Risk**: <potential impact>
  **Fix**: <concrete remediation>

### ℹ️ Info
Best practice suggestions for defense in depth.

- **`file:line`** — <suggestion>
  **Fix**: <concrete improvement>

### Dependency Audit
<Results of npm/pnpm audit if new dependencies were added, or "No new dependencies">

### Verdict
<PASS | FAIL | NEEDS_ATTENTION>
<justification>
```

## Rules

- ALWAYS fetch the actual PR diff — never review from memory
- ALWAYS explain the **risk** (what an attacker could do), not just the issue
- ALWAYS provide a concrete fix, not just "validate input"
- Flag hardcoded secrets as 🔴 Critical — always
- If new dependencies were added, run the package audit
- Don't flag test files for security issues (test fixtures are fine)
- Don't flag development-only code (devDependencies, scripts) unless it ships to production
