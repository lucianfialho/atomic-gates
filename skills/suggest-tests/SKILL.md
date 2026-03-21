---
name: suggest-tests
description: Analyze a PR diff and suggest missing tests — edge cases, integration gaps, and regression risks
args: pr_number
---

# Suggest Tests

Analyze code changes in a PR and suggest tests that are missing. Uses QA engineer expertise to identify untested paths, edge cases, and regression risks.

## Usage

```
/suggest-tests           — Analyze the current PR branch
/suggest-tests 42        — Analyze PR #42
```

Also works as `@claude suggest tests` in GitHub PR comments.

## Process

### 1. Get the changes

```bash
# Current branch
gh pr view --json number,title,body,files
gh pr diff

# Or specific PR
gh pr view <number> --json number,title,body,files
gh pr diff <number>
```

### 2. Detect test framework

Check the project for the testing setup:
- `vitest.config.*` or `vitest` in package.json → **Vitest**
- `jest.config.*` or `jest` in package.json → **Jest**
- `pytest.ini` or `pyproject.toml` with pytest → **pytest**
- `playwright.config.*` → **Playwright** (E2E)
- `cypress.config.*` → **Cypress** (E2E)

Also check existing test files for import patterns and conventions.

### 3. Analyze the diff

For each changed file, identify:

**New code that needs tests:**
- New functions or methods
- New API routes or Server Actions
- New React components with logic
- New utility/helper functions
- New database queries or mutations

**Edge cases to cover:**
- Empty/null/undefined inputs
- Boundary values (0, -1, MAX_INT, empty string, max length)
- Invalid types (string where number expected)
- Unicode, special characters, very long strings
- Concurrent operations (race conditions)
- Permission/auth edge cases
- Network failure scenarios

**Integration gaps:**
- New endpoints without request/response tests
- Database operations without transaction tests
- Auth flows without unauthorized tests
- File uploads without size/type validation tests

**Regression risks:**
- Modified functions that have existing tests (check if tests need updating)
- Changed API contracts (request/response shapes)
- Modified database schemas
- Changed validation rules

### 4. Output format

```markdown
## Suggested Tests

### Summary
<N> test suggestions across <M> files. Estimated effort: <low/medium/high>.

### Unit Tests

#### 1. <functionName> — <brief description>
**File**: `<path to where test should live>`
**Why**: <why this needs testing>
**Cases**:
- <test case description>
- <test case description>
- <test case description>

```<language>
// Skeleton test code
describe("<functionName>", () => {
  it("<test case>", () => {
    // arrange
    // act
    // assert
  });
});
```

### Integration Tests

#### 1. <endpoint/flow> — <brief description>
**File**: `<path to where test should live>`
**Why**: <why this needs testing>
**Cases**:
- <test case description>
- <test case description>

### Regression Risks

#### 1. <what changed> — <what might break>
**Existing tests**: `<path to existing test file>`
**Action**: <update existing test / add new case>
```

### 5. Prioritize suggestions

Order by impact:
1. **Critical**: New public API endpoints with no tests
2. **High**: Functions with complex logic or branching with no tests
3. **Medium**: Edge cases for existing tested functions
4. **Low**: Additional coverage for well-tested areas

## Rules

- ALWAYS fetch the actual PR diff — never suggest from memory
- ALWAYS check existing test files before suggesting (avoid duplicates)
- ALWAYS use the project's testing framework and conventions
- ALWAYS provide skeleton test code, not just descriptions
- Place test files following existing project conventions (e.g., `__tests__/`, `.test.ts` colocated, `tests/` directory)
- Skeleton code should be runnable — correct imports, realistic mock data
- Don't suggest tests for generated code, config files, or type-only changes
- Focus on behavior, not implementation details
