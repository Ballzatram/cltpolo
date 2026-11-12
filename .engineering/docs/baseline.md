# Universal engineering baseline

**MUST** is mandatory when applicable. **SHOULD** is the default; a departure requires a recorded rationale. **MAY** is optional. A mandatory control needs evidence or a valid approved waiver. A justified `not-applicable` review is appropriate only when the control's trigger does not exist.

## Control register

| ID | Requirement | Minimum acceptance evidence |
| --- | --- | --- |
| GOV-01 | MUST name a project owner, lifecycle status, risk tier, applicable profiles and exact standards version. | `.standards.json` and owner acknowledgement. |
| GOV-02 | MUST assess every applicable control, track gaps and keep exceptions expiring. | Dated audit with commit, reviewer, evidence links and waivers. |
| REPO-01 | MUST provide reproducible setup, run, test, build and release instructions; supported runtimes; purpose and non-goals. | A clean-clone walkthrough by someone other than the author where possible. |
| REPO-02 | MUST exclude secrets, generated output, caches and local configuration from version control; keep ownership, contribution and security guidance. | Tracked-file inspection, `.gitignore`, owner rules and docs. Ignore rules alone are insufficient. |
| ARCH-01 | MUST keep responsibilities separated, dependencies explicit and external integrations behind defined boundaries. | Short architecture note, dependency direction and review of changed boundaries. Avoid speculative frameworks. |
| ARCH-02 | MUST document material tradeoffs and failure behavior; maintain API/data compatibility deliberately. | Decision records for consequential choices, migration and compatibility tests. |
| CODE-01 | MUST use the ecosystem's formatter, lint and type/static checks as applicable. | Versioned configuration, clean output and required CI results. Tool exclusions are narrow and justified. |
| CODE-02 | MUST validate untrusted input at boundaries, handle expected errors explicitly, release resources, and bound external work with timeouts. | Error-path tests and code review. No empty exception handlers or silent fallback hiding failed work. |
| TEST-01 | MUST test observable behavior, important boundaries and failure paths; each bug fix adds a regression test when feasible. | Test cases linked to requirements and bugs; useful assertions that fail on incorrect behavior. |
| TEST-02 | MUST keep tests isolated and reproducible, enforce the declared coverage gate, and justify uncovered critical logic. | CI test report, branch coverage and review of missing branches. See testing policy. |
| BUILD-01 | MUST declare runtime/tool versions, dependencies and deterministic install instructions. Commit lockfiles for applications and dev/test environments. | Clean locked install and build; library dependency ranges tested separately. |
| CI-01 | MUST run required checks on every proposed code change and the protected branch, with timeouts and a stable final gate. | Workflow definitions plus a successful run on the candidate commit. |
| CI-02 | MUST protect merge and release paths, restrict pipeline credentials and review workflow changes. | Live repository settings, permission review and protected deployment environment when deployed. |
| SEC-01 | MUST prevent, scan for and respond to secret exposure; never embed production credentials in code, tests, logs or artifacts. | Secret scanning configured and exercised; private reporting route; rotation procedure. |
| SEC-02 | MUST scan dependencies and source for relevant vulnerabilities, review new dependencies and remediate findings by severity. | Current successful scanner runs, triage records and approved exceptions. |
| SEC-03 | MUST authorize every protected action at the server/trust boundary and minimize collection/exposure of sensitive data. | Authorization denial tests, data-flow review and retention/redaction rules. N/A needs evidence of no protected resources or sensitive data. |
| DOC-01 | MUST keep public behavior, configuration and operational documentation consistent with code. | Working examples, sample configuration without secrets, release/change notes. |
| REL-01 | MUST identify releases by immutable source revision, validate distributable artifacts and document rollback or recovery. | Artifact smoke test, release record and rehearsed recovery for deployed systems. |
| OPS-01 | When deployed, MUST define owner, health signals, useful logs, alerts and service objectives proportional to impact. | Runbook and an exercised alert/health check. |
| DATA-01 | When persistent data exists, MUST test migrations and recovery, define retention and restrict access. | Restore evidence, migration tests and data ownership. A backup without a restore test is insufficient. |
| UX-01 | When people interact with a UI, MUST cover accessibility, loading/empty/error states, privacy and supported devices. | Keyboard/manual accessibility review and behavioral tests. |
| AI-01 | When AI assists development, MUST review and independently verify generated code and dependencies. | Reviewer notes, command results, negative tests and disclosed limitations. |

Profiles add requirements under these IDs; choosing a language does not replace the baseline. Reviewers must record profile-specific evidence as well as this register.

## Risk tiers

| Tier | Select when | Extra obligations |
| --- | --- | --- |
| local | Local tools, prototypes and non-sensitive personal utilities with no public deployment. | Baseline, relevant tests and reproducible setup. A solo maintainer may self-review, explicitly recorded. |
| standard | Shared apps, ordinary public services or production automation. | Independent review where staffing permits; monitored deployment; tested recovery; staging or representative pre-release validation. |
| critical | Money movement, sensitive/regulated data, safety-related behavior, privileged infrastructure, or material business impact. | Independent approval for sensitive changes, threat model, abuse tests, restore rehearsal, artifact provenance, explicit performance/reliability targets and selected external security requirements. |

Select the highest applicable tier. An undeployed local program processing sensitive personal data can still be critical. These are internal tiers, not legal classifications. Record applicable external obligations separately.

## Definition of ready and done

Before implementation: state the user-visible outcome, acceptance examples, risks, data/API impact and verification plan. For a small fix this can be a few sentences in a PR; substantial designs need a decision record.

Before merging: satisfy acceptance examples; run relevant checks; review failure and abuse paths; update documentation and migrations; record residual risks. Before release: verify the actual distributable, environment configuration and recovery route. Avoid unrelated cleanup and unrequested architecture.
