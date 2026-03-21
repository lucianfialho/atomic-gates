# Backend Review Rules

Loaded when the diff contains `route.ts`, `route.js`, `actions.ts`, `actions.js`, or files in `api/` directories.

## API Design
- Correct HTTP status codes (201 for creation, 404 for not found, 422 for validation)
- Consistent error response format across endpoints
- Pagination for list endpoints
- Input validation on all request bodies
- Rate limiting on public endpoints

## Error Handling
- Never expose internal errors to clients (no stack traces in responses)
- All async operations have try/catch or error boundaries
- External API calls have timeout and retry logic
- Graceful degradation when dependencies fail

## Database
- All queries parameterized (no string concatenation for SQL)
- Transactions for multi-step operations
- Indexes exist for frequently queried columns
- Migrations are reversible
- No N+1 queries (use joins or batch fetching)

## Authentication & Authorization
- Protected routes check auth before any logic
- Authorization checked (not just authentication)
- Tokens validated (signature, expiration)
- Session management is secure
