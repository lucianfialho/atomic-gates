---
name: ux-review
description: UX-focused review of UI changes — heuristics, accessibility, interaction design, visual hierarchy
args: pr_number
---

# UX Review

Review UI changes in a PR against UX best practices, accessibility standards, and interaction design principles.

## Usage

```
/ux-review               — Review the current PR branch
/ux-review 42            — Review PR #42
```

Also works as `@claude ux-review` in GitHub PR comments.

## Process

### 1. Get the changes

```bash
gh pr view --json number,title,body,files
gh pr diff
```

Focus on UI-relevant files: `.tsx`, `.jsx`, `.css`, `.scss`, `.module.css`, `.html`, and component files.

If no UI files changed, report: "No UI files found in this PR. UX review not applicable."

### 2. Evaluate against Nielsen's Heuristics

For each UI change, check the applicable heuristics:

1. **Visibility of system status** — Does the UI show loading, progress, or feedback?
2. **Match between system and real world** — Does the language make sense to users?
3. **User control and freedom** — Can users undo, cancel, or go back?
4. **Consistency and standards** — Does it match the existing design system?
5. **Error prevention** — Does the UI prevent mistakes (confirmation, validation)?
6. **Recognition over recall** — Are options visible, not hidden in menus?
7. **Flexibility and efficiency** — Are there shortcuts for power users?
8. **Aesthetic and minimalist design** — Is every element necessary?
9. **Help users recover from errors** — Are error messages actionable?
10. **Help and documentation** — Are tooltips or help text available where needed?

### 3. Accessibility check (WCAG 2.1 AA)

- **Semantic HTML**: Using `<button>`, `<nav>`, `<main>` etc. instead of styled divs?
- **ARIA labels**: Do interactive elements have accessible names?
- **Keyboard navigation**: Can all interactive elements be reached with Tab?
- **Focus management**: Do modals trap focus? Is focus restored on close?
- **Color contrast**: Do text/background combinations meet 4.5:1 ratio?
- **Color alone**: Is information conveyed by more than just color?
- **Touch targets**: Are buttons at least 44x44px on mobile?
- **Alt text**: Do images have meaningful alt attributes?

### 4. Interaction & state coverage

- **Loading state**: Is there a skeleton, spinner, or progress indicator?
- **Error state**: What does the user see when something fails?
- **Empty state**: What shows when there's no data?
- **Edge cases**: Long text, missing images, single item, many items?
- **Responsive**: Does it work at 320px? 768px? 1920px?
- **Transitions**: Are state changes animated or jarring?

### 5. Output format

```markdown
## UX Review

### Summary
<1-2 sentence overview of UX quality>

### Accessibility
- ⚠️ **`file:line`** — <issue>
  **Fix**: <concrete suggestion>

### Interaction Design
- 💡 **`file:line`** — <issue>
  **Fix**: <concrete suggestion>

### Visual Consistency
- ℹ️ **`file:line`** — <issue>
  **Fix**: <concrete suggestion>

### Missing States
- ⚠️ **`file:line`** — <which state is missing: loading/error/empty>
  **Fix**: <what to add>

### Verdict
<APPROVE | NEEDS_WORK | COMMENT>
<1 sentence justification>
```

## Rules

- ALWAYS fetch the actual PR diff — never review from memory
- ALWAYS check for missing states (loading, error, empty)
- NEVER sacrifice usability for aesthetics in suggestions
- NEVER suggest changes that are purely subjective (unless backed by a heuristic)
- Be practical — suggest fixes that fit the project's existing design system
- Skip UX review entirely if no UI files changed
- Accessibility issues are always ⚠️ Warning or higher
