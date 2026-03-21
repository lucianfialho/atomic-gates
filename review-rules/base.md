# Base Review Rules

Always loaded for every review, regardless of file type.

## Always Check
- New features have corresponding tests
- No hardcoded secrets, API keys, or credentials
- Error handling exists for external API calls
- Functions have clear single responsibility
- No console.log left in production code (use proper logging)

## Style
- Prefer early returns over nested conditionals
- Use descriptive variable names (no single-letter vars except loop counters)
- Keep functions under 50 lines
- Prefer composition over inheritance

## Skip
- Generated files (prisma client, node_modules, .next, dist)
- Lock files (package-lock.json, pnpm-lock.yaml)
- Configuration files unless security-relevant
