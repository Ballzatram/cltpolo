# Standards assessment

Overall: **not-conforming — initial adoption implemented; review and legacy gaps remain**. No approved waivers have been invented.

- Framework: 1.0.0
- Automated assessment: Codex, updated 2026-11-12; owner authorized merge; independent product/operations review remains pending
- Owner: Ballzatram
- Baseline revision: `45e0e0341a97a1c54135c9db8b24f7320e918d1c`
- Profiles: python, other-languages, web, services
- Risk: standard

| Control | Status | Evidence / remaining work |
| --- | --- | --- |
| AI-01 | pending | Automated changes and preservation boundaries were reviewed. Independent maintainer review remains required. |
| ARCH-01 | pass | Existing component and preservation boundaries are recorded; no new runtime service or architecture was introduced. |
| ARCH-02 | pending | Requires project-specific evidence and maintainer review. |
| BUILD-01 | pending | Requires project-specific evidence and maintainer review. |
| CI-01 | pass | Pinned PR/default/merge-group checks were exercised; successful final-head Engineering Standards CI is required before merge. See docs/merge-verification.md and the linked PR checks. |
| CI-02 | pass | Live default-branch protection was applied and read back: PR required, strict standards-gate bound to GitHub Actions, administrators enforced, force pushes/deletion denied. Solo-owner approval count is zero; deployment-environment review remains separate. |
| CODE-01 | fail | Native syntax/type checks are retained where present. Full legacy formatting and strict static-analysis adoption remain a tracked gap; no broad suppression was introduced. |
| CODE-02 | pending | Requires project-specific evidence and maintainer review. |
| DATA-01 | pending | Requires project-specific evidence and maintainer review. |
| DOC-01 | pending | Requires project-specific evidence and maintainer review. |
| GOV-01 | pass | Owner, lifecycle, risk, profiles and exact policy version are declared; GitHub owner access was verified. |
| GOV-02 | pending | Requires project-specific evidence and maintainer review. |
| OPS-01 | pending | Requires project-specific evidence and maintainer review. |
| REL-01 | pending | Requires project-specific evidence and maintainer review. |
| REPO-01 | pending | Requires project-specific evidence and maintainer review. |
| REPO-02 | pass | Contribution/security guidance, owner rules and local/generated-file exclusions are present. Current committed-source scan was reviewed. |
| SEC-01 | pending | Checked-out source scan passed with narrowly reviewed false positives. CI scans full history; reporting route needs operational verification. |
| SEC-02 | pending | Executed dependency scans are listed below. Whole-project source-security coverage and triage need review; dependency scanning is not a full security audit. |
| SEC-03 | pending | Requires project-specific evidence and maintainer review. |
| TEST-01 | pending | Real regression evidence is recorded below. Review completeness against product acceptance and denied/failed behavior. |
| TEST-02 | fail | Existing projects do not yet have a source-inclusive branch-coverage ratchet satisfying the shared policy. No threshold was lowered or waiver self-approved. |
| UX-01 | pending | Requires project-specific evidence and maintainer review. |

## Executed checks and preservation

118 Node model/worker tests passed. The Python source/pipeline suite ran 73 cases with one existing skip. Browser results are recorded separately when available. Runtime code, property data, payment rules and remote-refresh behavior are unchanged. No live payment or refresh was executed.

Action references were pinned to verified commits for their existing tags; existing deployment triggers and behavior were retained. Workflow timeouts bound unattended jobs. The shared policy auditor does not execute commands from the manifest. New engineering jobs never deploy or use production credentials. Current-source scans were performed on shallow checkouts; full-history CI results must be reviewed.

## Remediation backlog

| Control | Remaining work | Owner | Target |
| --- | --- | --- | --- |
| CODE-01 | Adopt missing format/static checks in focused, tested changes | Ballzatram | Before full conformance |
| TEST-02 | Measure source/branch coverage, review critical branches and establish a ratchet | Ballzatram | Before full conformance |
| CI-01 / CI-02 | Verify candidate runs and hosted protection/environment settings | Ballzatram | Before merge |
| SEC-01 / SEC-02 | Review full-history scan, source-security scope, findings and reporting route | Ballzatram | Before merge/release |
| OPS-01 / DATA-01 / UX-01 | Complete applicable recovery, monitoring and manual accessibility reviews | Ballzatram | Before release |

Native-platform and product-specific checks that were not executed remain pending. Specification-only repositories must import real source and select its actual stack before runtime controls can be assessed.

## Merge-time evidence

See [merge verification](merge-verification.md) for measured performance, hosted enforcement, source preservation and current coverage evidence. Residual failures/pending reviews above remain explicit; merging the adoption controls is not a conformance certificate.
