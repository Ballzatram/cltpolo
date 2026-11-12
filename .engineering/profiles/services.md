# Services, APIs and workers

Extends ARCH-02, SEC-03, OPS-01 and DATA-01.

- MUST define request/event schemas, validation, error semantics, pagination, versioning and compatibility expectations. Document API contracts, using OpenAPI or an equivalent where appropriate.
- MUST test authentication and authorization per action/resource, including cross-user/tenant denial and administrative boundaries.
- MUST bound work with timeouts, payload limits, rate/concurrency controls and safe retries. Define idempotency and partial failure behavior for state-changing requests.
- MUST test database transactions and supported migration paths against the actual database family. Do not substitute an in-memory database when its semantics differ materially.
- MUST define health/readiness, structured logs, correlation, actionable metrics, service objectives and safe shutdown.
- Workers MUST document delivery semantics, duplicate handling, retry budgets, poison-message handling, dead letters and replay. Exercise worker restart and partially completed work.
- MUST validate deployment configuration, recovery and secrets in a representative environment before production release.

Evidence: contract/integration tests, abuse/denial cases, failure and replay scenarios, runbook, monitoring and recovery exercise.
