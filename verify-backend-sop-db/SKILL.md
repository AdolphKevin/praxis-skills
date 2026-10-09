---
name: verify-backend-sop-db
description: Validate backend business SOPs through real API, gRPC, or service entry points against a production-compatible database with deterministic fixtures and exact response and persistence assertions. Use when users ask for SOP DB-level absolute-value verification, backend interface database integration tests, proof of record selection and side effects, or a durable regression test for a database-backed business flow. Keep the interface test in the target repository and use the bundled PostgreSQL runner; do not substitute isolated SQL, repository-only tests, mocks, compilation, or skipped tests.
---

# Verify Backend SOP Against DB

Turn a business SOP into a durable backend interface integration test. Keep the test in the target repository so future changes rerun the same contract.

## Establish the contract

Write down exact observable outcomes before editing:

- backend entry point and authenticated tenant context;
- selected record ID and response reason;
- rows inserted, updated, or intentionally unchanged;
- counters, messages, audit records, or state transitions;
- negative branches and state changes requiring revalidation.

Treat these as absolute values. Do not settle for “no error”, non-empty output, or approximate counts.

## Build the persistent test

1. Reuse the repository's existing API, gRPC, or service DB test harness.
2. Invoke the real backend entry point. Do not call the target SQL or repository method as the acceptance boundary.
3. Use the production database engine, compatible column types, constraints, and migrations.
4. Create isolated deterministic fixtures in a temporary schema or database.
5. Assert the exact response payload, reason, selected entity, and database side effects.
6. Cover at least:
   - the intended success path;
   - a newer but ineligible record;
   - no eligible record;
   - tenant, customer, or resource mismatch;
   - already-processed and retryable states;
   - final revalidation when the SOP includes a read-then-act gap.
7. Keep the test file in the repository after it passes. Remove only runtime data and temporary infrastructure.

Mocks may replace dependencies outside the validation boundary, such as third-party APIs. Never mock the target database path or backend entry point.

## Run with PostgreSQL

Use the bundled runner when the project does not already provide a real test database:

```bash
~/.codex/skills/verify-backend-sop-db/scripts/run_postgres_test.sh \
  go test ./internal/service -run '^TestTargetSOPPostgres$' -count=1 -v
```

The runner uses `TEST_POSTGRES_DSN` when present. Otherwise it starts an isolated `postgres:16-alpine` container, exports `TEST_POSTGRES_DSN` and `DATABASE_URL`, runs the command, then removes the container.

Set `SOP_DB_ENV` when the project expects another environment variable:

```bash
SOP_DB_ENV=DB_DSN ~/.codex/skills/verify-backend-sop-db/scripts/run_postgres_test.sh \
  go test ./... -run '^TestTargetSOPPostgres$' -count=1 -v
```

For a non-PostgreSQL system, follow the same contract and add a durable engine-specific runner to this Skill instead of creating a disposable task script.

## Challenge failures

Treat a real DB failure as evidence. Trace the earliest divergence across schema mapping, query construction, business selection, response conversion, and persistence. Fix the root cause, rerun the interface test, then run the nearest repository, business, and service regressions.

## Completion gate

Completion requires all of the following:

- the persistent test calls the real backend interface;
- the real database test executes and passes;
- exact response and database values are asserted;
- negative and no-write branches are covered;
- temporary schemas and containers are cleaned up;
- the final report includes the executed command and PASS result.

Report `BLOCKED`, not PASS, when the test is skipped, the required database cannot run, or only compilation succeeds.
