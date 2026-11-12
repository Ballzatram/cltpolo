# Engineering Standards

A shared engineering baseline for every repository: readable code, meaningful tests, safe delivery, clear ownership, and evidence that it works.

**Framework version: 1.0.1 — 2026-11-11.** This is an internal engineering policy, informed by published guidance. It is not a certification or a claim of NIST, OWASP, or regulatory compliance.

## Start here

1. Read [the mandatory baseline](docs/baseline.md).
2. Select all applicable [project profiles](profiles/README.md) and a risk tier.
3. For a new Python or TypeScript project, use the scaffolder below. For an existing repo, follow [adoption and remediation](docs/adoption.md).
4. Run the structural audit, then complete the evidence-based review in `docs/audit.md`. Both are required; a file's existence does not prove its contents are correct.

```powershell
# Run from this Standards workspace; requires Python 3.12+.
python tools/scaffold.py ../my-project --language python --owner Ballzatram
python tools/scaffold.py ../my-web-project --language typescript --owner Ballzatram

# Inspect an existing repository without executing its code or changing it.
uv run --locked python tools/audit.py ../existing-project
uv run --locked python tools/audit.py ../existing-project --json

# Validate this framework's tools and templates.
uv sync --locked
uv run --locked python tools/check.py
# Also validate freshly generated starters; needs the pinned Node/npm toolchain.
uv run --locked python tools/validate_starters.py
```

The scaffolder accepts a new destination or an empty directory only. It includes a versioned `.engineering/` snapshot so projects and coding agents can read the exact standard offline. It does not install dependencies, initialize Git, publish anything, or configure remote repository settings. Follow the generated README to finish setup.

## What every project adopts

| Layer | Purpose | Where |
| --- | --- | --- |
| Universal baseline | Requirements that apply to every code repo | [Baseline](docs/baseline.md) |
| Language and product profiles | Extra requirements for the stack and product | [Profiles](profiles/README.md) |
| Testing and delivery | Test design, merge gates, pipeline and release rules | [Testing](docs/testing.md), [CI/CD](docs/ci-cd.md) |
| Security and operations | Dependencies, secrets, privacy, recovery and monitoring | [Security](docs/security.md), [Operations](docs/operations.md) |
| AI-assisted development | Rules for agents, generated code and verification | [AI development](docs/ai-development.md) |
| Governance | Versioning, risk, waivers and adoption | [Adoption](docs/adoption.md) |
| Evidence | Control-by-control assessment and remediation | [Audit template](templates/common/docs/audit.md) |

## What is included

- Stable control IDs with acceptance evidence, rather than an unscored list of suggestions.
- Python and TypeScript starter projects with formatter, lint, strict types, tests, coverage, dependency audit, build, and GitHub Actions configurations.
- Profiles for web/UI, services/APIs, libraries, CLIs, data/ML, infrastructure, mobile/desktop, and other languages. These profiles specify requirements; executable starters are currently Python and TypeScript only.
- A read-only structural audit that reports missing prerequisites and invalid or expired waivers. It deliberately does not claim to verify behavior, security, coverage quality, or remote branch settings.
- Agent instructions, pull request template, ownership template, dependency updates, architecture notes and a runbook template.

## Definition of done

A project is **up to standard** when every applicable mandatory control has current evidence, required checks pass on the candidate commit, repository settings are verified, and any exception has an owner, mitigation, approval and expiry. New projects start with pending manual reviews; copying the template never awards a passing audit.

The initial defaults are opinionated, including 80% branch-inclusive coverage and a 90-day maximum waiver. They are our policy choices, not universal industry thresholds. Small projects keep the baseline; higher-risk systems add stronger safeguards.

For repeatable requests to coding agents, use [the adoption prompts](docs/agent-prompts.md).

## Maintaining this framework

Change standards through a reviewed pull request; record changes in [CHANGELOG.md](CHANGELOG.md). Consumers pin a version and upgrade explicitly. Review tool pins and source links at least quarterly, and security advisories sooner. [Sources](docs/sources.md) records the authoritative references and the scope of their influence.

This workspace has not been published to a Git host. After publication, record its canonical URL in consumer manifests and documentation; keep the vendored version as the reproducible reference.

See [initial verification](docs/verification.md) for executed checks and remaining hosted/manual reviews.
