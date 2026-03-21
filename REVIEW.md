# Code Review Guidelines

## Always check
- New features have corresponding tests
- No hardcoded secrets, API keys, or credentials
- Error handling exists for external API calls
- Database queries are parameterized (no SQL injection)
- User input is validated and sanitized
- Functions have clear single responsibility
- No console.log left in production code (use proper logging)

## Style
- Prefer early returns over nested conditionals
- Use descriptive variable names (no single-letter vars except loop counters)
- Keep functions under 50 lines
- Prefer composition over inheritance

## Performance
- No N+1 queries in database operations
- Large lists should be paginated
- Images should use next/image or equivalent optimization
- Avoid synchronous blocking operations in request handlers

## Security
- Authentication checks on all protected routes
- Rate limiting on public API endpoints
- CSRF protection on mutations
- No sensitive data in client-side code or localStorage

## Skip
- Generated files (prisma client, node_modules, .next, dist)
- Lock files (package-lock.json, pnpm-lock.yaml)
- Configuration files unless security-relevant
