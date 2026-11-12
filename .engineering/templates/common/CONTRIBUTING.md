# Contributing

Read README.md, AGENTS.md, `.standards.json` and the pinned `.engineering/` policies. Keep changes focused and describe acceptance examples, verification and delivery risks in the pull request.

Use the runtime and setup commands in README.md. Run every executable string in `.standards.json` before requesting review. An explicit unavailable/not-applicable object is a reviewed status with a reason and tracking link, not a shell command or a passing check; unavailable mandatory checks still block full conformance. Formatters may fix files locally; CI checks must fail on differences rather than quietly modifying them.

Do not commit credentials, personal data or generated output. Review unfamiliar dependencies and lockfile changes. Changes to behavior need meaningful tests; bug fixes need a regression test where feasible. Update architecture, API/configuration and runbook documentation as needed.

The project owner chooses the project's license/distribution terms before external distribution; this template grants no license automatically. Configure review and protected branch requirements before treating CI as an enforced merge gate.
