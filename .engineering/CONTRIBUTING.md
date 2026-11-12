# Contributing

Use a focused pull request describing the problem, resulting behavior, validation and migration impact. Read [the baseline](docs/baseline.md), [testing rules](docs/testing.md) and [AI rules](docs/ai-development.md).

Install a supported Python and uv, run `uv sync --locked`, then `uv run --locked python tools/check.py`. The checker runs formatting, lint, strict typing, tests, dependency audit and the structural audit. It does not evaluate remote GitHub settings. A network outage in vulnerability checking is a failed/incomplete check, not evidence of safety.

When editing templates, generate fresh Python and TypeScript projects and run their documented checks. Keep new dependencies purposeful, recorded in the lockfile and reviewed. Do not modify the framework version solely for a typo; record substantive policy changes in CHANGELOG.md and release them deliberately.

`uv run --locked python tools/validate_starters.py` creates temporary projects, installs their locked dependencies and runs their real checks and artifact smoke tests. It needs uv 0.13.7 and the Node/npm versions pinned in `templates/typescript/`. These orchestration scripts are checked by execution rather than artificial unit coverage.

Before publication, configure ownership, security reporting and repository rules using [CI/CD](docs/ci-cd.md). No external review or remote enforcement has been claimed for this initial local repository.
