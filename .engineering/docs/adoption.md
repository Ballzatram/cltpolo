# Adoption, audits and governance

## New projects

Choose a language starter or copy `templates/common/` and supply an ecosystem-native toolchain. Read all applicable profiles, set owner and risk, and pin framework version 1.0.1 in `.standards.json`. Python and TypeScript starters include a `.engineering/` snapshot with the auditor and complete policies. For other stacks, copy this repo's VERSION, docs and profiles into `.engineering/` and record that path as `framework_source`; optionally also record the canonical URL and immutable revision. The current auditor checks an in-repo snapshot only.

Complete setup, lock dependencies and run all checks. Configure hosted settings from CI/CD policy. Replace generated purpose, architecture, security route and audit evidence with project facts. Do not claim adoption is complete while review rows remain pending.

## Existing projects

1. Inventory stack, runtime versions, users, data, deployments and owners. Choose every applicable profile and the highest applicable risk tier.
2. Run `uv run --project PATH_TO_STANDARDS --locked python PATH_TO_STANDARDS/tools/audit.py PATH_TO_REPO` from any working directory. It is read-only and never runs the target's commands. A missing manifest is an adoption gap, not a reason to skip review.
3. Copy/merge the common files and selected configuration intentionally. Never replace existing manifests, lockfiles or workflows wholesale. Map equivalent tools rather than forcing a needless rewrite.
4. Complete `docs/audit.md` for every baseline control and relevant profile. Record status, evidence, reviewed commit, reviewer and date. Keep evidence immutable/reproducible where possible. External or hosted settings need direct inspection.
5. Create a prioritized remediation list with control ID, specific gap, risk, owner, target date and verification. First: exposed secrets, exploitable vulnerabilities, data-loss paths and unprotected production credentials. Next: reproducible builds, tests for critical behavior and blocking CI. Then: maintainability, documentation and expanded coverage.
6. Deliver small remediation PRs. For legacy debt, establish a measured baseline and prohibit regressions. Use bounded waivers instead of silently disabling checks. Reassess after each remediation.
7. Accept only when all applicable MUST controls pass or have valid approved exceptions. Report `conforming-with-waivers` separately from `conforming`; unresolved failures or pending reviews remain `not-conforming`.

## Evidence rules

Audit statuses are `pass`, `fail`, `pending`, `not-applicable`, and `waived`. A pass identifies what was inspected or executed and the relevant commit/run. N/A explains why the trigger is absent and who reviewed that conclusion. A waiver references an approved exception. `pending` is never counted as passing. Do not compute a blended score that hides a failed critical control.

Repeat the review before the first release, after major architecture/data/deployment changes, after a significant incident and at least quarterly for maintained deployed projects. A previous pass can expire when code, threat exposure, dependencies or hosted settings change. Local structural checks are only one input to this assessment.

## Exceptions

Keep machine-readable exceptions in `docs/waivers.json` as an array. Each entry contains `control`, `reason`, `owner`, `approved_by`, `expires` (ISO date), `mitigation`, and `tracking`. Maximum remaining validity at approval is 90 days; reapproval requires a new risk decision. The auditor rejects unknown controls, missing fields, expired dates and dates more than 90 days ahead, but cannot verify approver identity or historical renewal length.

An exception expires at the start of its expiry date in the audit process's local calendar; CI runners usually use UTC. Use a consistent organizational timezone for formal reviews. Critical systems require independent approval; solo local projects may record self-approval. Never use an exception to normalize an active credential leak or known exploited exposure; contain those first.

```json
[
  {
    "control": "TEST-02",
    "reason": "Legacy coverage is 63%; new code remains at the 80% gate.",
    "owner": "actual-owner",
    "approved_by": "actual-reviewer",
    "expires": "YYYY-MM-DD",
    "mitigation": "Critical paths covered; coverage must not regress.",
    "tracking": "Link to a remediation issue with a target date"
  }
]
```

The structural auditor never converts a missing requirement into a passing result because a waiver exists. Waivers are review evidence, and a reviewer decides whether they cover the actual gap.

Monorepos may declare optional `components` in the manifest. Each entry names its in-repo `path`, selected `profile`, `dependency_manifest` and `lockfile` relative to that component. The auditor checks those declared files instead of requiring a second package manifest at the repository root for that language. This supports existing requirements-based Python and nested npm projects without rewriting their runtime configuration. Dependency resolution, typing, behavior and component coverage still need verification.

`test_directories` can name existing in-repo test locations such as `backend/tests` or a native platform's test target. A repository containing plans but no imported application source may declare `repository_kind: "specification"`; its runtime-test check is reported as requiring review, never as executed/passing tests. Reviewers must verify that classification and reassess when source is imported.

## Versions and reuse

The command register accepts executable strings or explicit status objects with `status` (`unavailable` or `not-applicable`), `reason` and `tracking`. The auditor emits REVIEW for status objects. These records are never evidence that a check ran; an unavailable mandatory check remains an adoption gap. Do not use prose as an executable command or label absent checks as passing.

A specification-only application repository may vendor this framework's Python tools. Its application runtime remains absent, while the complete `.engineering/` package has its own Python profile, locked tools and tool regression/static checks under the existing CODE-01 and TEST-01 obligations. Test the vendored tool package independently of application classification.

The canonical policy lives in this repository. Until published, consumers use the scaffolded `.engineering/` snapshot. Keep its VERSION, docs and auditor together; do not edit the copied baseline to weaken a consumer's obligations. Project-specific additions belong in the consumer's own docs and AGENTS.md.

After publication, add the canonical repository URL to consumer manifests. Pin a release/commit, not `main`. A major version adds or changes mandatory obligations; a minor version adds compatible guidance/profiles; patches clarify without changing obligations. Update consumers through explicit PRs, review the changelog, refresh snapshots and tools together, and rerun audits. Dependency update bots do not update a vendored snapshot automatically.

Remote reusable workflows may later centralize CI, pinned by full commit SHA. Keep local commands runnable and document how the workflow's inputs map to this baseline. Do not require an unpublished URL in order to build a project.
