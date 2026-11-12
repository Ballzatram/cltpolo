# Contributing

Read README.md, AGENTS.md, `.standards.json` and the pinned `.engineering/` policies. Keep changes focused and describe acceptance examples, verification and delivery risks in the pull request.

Use the runtime and setup commands in README.md. Run every executable string in `.standards.json` before requesting review. Explicit unavailable/not-applicable records are status objects with reason/tracking, never shell commands or passing results; unavailable mandatory checks still block full conformance. Formatters may fix files locally; CI checks must fail on differences rather than quietly modifying them.

Do not commit credentials, personal data or generated output. Review unfamiliar dependencies and lockfile changes. Changes to behavior need meaningful tests; bug fixes need a regression test where feasible. Update architecture, API/configuration and runbook documentation as needed.

The project owner chooses the project's license/distribution terms before external distribution; this template grants no license automatically. Configure review and protected branch requirements before treating CI as an enforced merge gate.

Project-specific verification: see `docs/standards-adoption.md`. Existing runtime/tooling is preserved.
