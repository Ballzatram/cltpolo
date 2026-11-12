# Testing standards

Impressive coverage is not evidence of correct behavior. Start with the contract: given an input and state, what observable result, error or side effect should occur?

## Required test design

- Unit tests cover domain decisions and boundaries. Integration tests exercise real adapters, databases, serialization and transactions where those exist. End-to-end tests cover a small set of critical user journeys for applications with multiple interacting layers.
- Include invalid, empty and extreme input; missing permissions; tenant isolation; partial failures; timeouts; retries; duplicate requests; cancellation and resource cleanup where relevant.
- For a bug, demonstrate that the regression test fails before the fix when practical. Review a deliberately wrong implementation or mutation for critical assertions.
- Mock external boundaries rather than the logic under test. Verify important integrations against disposable real services or contract fixtures; do not assume mocked SDK behavior is accurate.
- No production credentials, production writes or identifiable production data. Use synthetic fixtures, isolated databases and explicit cleanup. Tests must not depend on order, wall-clock timing, an unseeded random sequence or live internet by default.
- Mark intentional external/integration suites, document prerequisites and run the applicable suites before release. A unit-only green build does not establish service readiness.
- Retrying a flaky test does not fix it. Quarantine only with a tracking issue, owner, expiry and replacement protection for the affected behavior. Fail on unexpected passes of expected failures.

## Gates

New Python and TypeScript projects start with **80% combined line/branch coverage**, measured on shipped first-party source, with exclusions justified. Maintain or improve the baseline in existing projects; use a temporary waiver and a ratchet if they begin below it. Coverage must include unexecuted source files. Critical authorization, money calculations, data loss prevention and recovery decisions need scenario coverage regardless of percentage.

Formatting, lint, types, tests and builds are blocking. An empty test suite, missing coverage report, failed test collection or unavailable scanner is a failure. Do not lower thresholds, ignore entire modules or regenerate snapshots solely to obtain green checks.

Public libraries test the declared runtime range and supported platform differences. Services validate migrations from a supported prior schema and transactions against the real database family. UIs test browser/device support, keyboard navigation and critical flows. Add load, property, fuzz or mutation tests when the failure cost warrants them.

For very small scripts a few direct behavior tests may be enough. Do not build test scaffolding that merely mirrors trivial implementation details.
