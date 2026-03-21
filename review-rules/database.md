# Database Review Rules

Loaded when the diff contains migration files, schema files, or ORM model changes.

## Migrations
- Migration is reversible (has a down/rollback step)
- No data loss in migration (additive preferred over destructive)
- Large table changes consider zero-downtime patterns
- Default values provided for new non-nullable columns

## Queries
- All queries parameterized
- No N+1 queries (use joins, includes, or batch fetching)
- Indexes exist for WHERE, ORDER BY, and JOIN columns
- LIMIT/OFFSET or cursor-based pagination for large result sets

## Transactions
- Multi-step operations wrapped in transactions
- Transaction isolation level appropriate for the use case
- Deadlock-prone patterns avoided (consistent lock ordering)

## Schema
- Column types appropriate for the data (no text for booleans)
- Foreign keys defined for referential integrity
- Cascading deletes are intentional and documented
- Timestamps (created_at, updated_at) present on business entities
