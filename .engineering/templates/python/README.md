# __PROJECT_NAME__

Owner: __OWNER__. Status: prototype; standards review pending.

Replace this introduction with purpose, users, non-goals and usage. The label-normalization function is a tested example, not completed product functionality. Review `docs/architecture.md`, `docs/runbook.md` and `docs/audit.md` before release.

## Setup and checks

Requires Python 3.12–3.14 and uv 0.13.7. Development defaults to 3.14. Install uv using its official installation guidance, then:

```text
uv sync --locked
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy src/starter_package
uv run --locked pytest
uv run --locked pip-audit --skip-editable --vulnerability-service osv
uv run --locked python -m build --no-isolation
uv run --locked python tools/smoke.py
python .engineering/tools/audit.py .
```

To format locally: `uv run --locked ruff format .`. Update dependencies intentionally with `uv lock --upgrade`, review the diff and rerun checks. Do not use a lock update to bypass a failed compatibility or security review.

CI verifies each supported Python on Ubuntu and the default runtime on Windows. Add platforms or product integration/E2E tests when the project claims them. The wheel smoke test installs into a fresh environment outside this checkout; change its assertion as the API changes.

Builds use the build backend and transitive tools already installed from the lockfile with build isolation disabled. Run the locked sync first; do not substitute an arbitrary active environment for the documented build environment.

Dependency auditing uses OSV and skips the editable first-party package, which has no published advisory identity; its installed third-party dependencies and development tools are still scanned. First-party source/security review remains a separate requirement.

## Standards and release

`.standards.json` pins the framework to the bundled `.engineering/` snapshot. Add every applicable product profile and select the correct risk tier; the initial language-only/local setting is provisional. The structural audit is not a full conformance review.

Before release: replace documentation prompts, choose license/distribution terms, configure actual CODEOWNERS and hosted branch/security settings, install secret scanning and complete the control/profile assessment. The example workflow does not deploy. A built wheel is not automatically published.
