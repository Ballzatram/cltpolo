# CI, repository and release standards

## Required pull request pipeline

Run on pull requests and changes to the default branch. If merge queues are enabled, include the queue event and test the queued revision. Do not attach path filters to the required final gate unless an always-running gate handles skipped work correctly.

1. Check out the candidate commit with read-only permissions and no persisted credentials.
2. Set up explicit runtime/tool versions and install with a lockfile freshness check.
3. Run structural policy checks, formatting, lint, type/static checks and behavior tests with coverage.
4. Run dependency vulnerability and secret scans. Add source analysis appropriate to the language; Python starters include selected Ruff security rules. TypeScript's ESLint rules alone are not a security scanner.
5. Build and smoke-test the actual installable artifact; test supported runtimes/platforms.
6. Have an always-running final gate fail if any required job failed, was cancelled or unexpectedly skipped.

Name checks uniquely; set job timeouts and cancellation for superseded PR runs. Do not cancel an in-progress production deployment as a side effect of PR concurrency. Capture diagnostic reports without secrets and choose a documented retention period.

## Pipeline security

- Pin external GitHub Actions to verified full commit SHAs and review dependency update PRs. Pin tools independently; an action pin alone does not pin the tool it downloads.
- Use `permissions: contents: read` by default. Give write permissions only to the specific trusted job that needs them. Prefer short-lived federated credentials for cloud access.
- Never run untrusted PR code with production secrets or a privileged `pull_request_target` context. Do not interpolate attacker-controlled PR titles, branch names or payloads into shell code; pass values through environment variables and quote them.
- Treat dependency installation hooks, build scripts and test commands as code execution. Use disposable runners for untrusted contributions; do not expose a persistent privileged self-hosted runner.
- Separate verification from deployment. Deploy only a trusted approved revision/artifact. Protect environment secrets and deployment approvals. Limit token scope, cache trust and artifact reuse across trust boundaries.

## GitHub settings that files cannot enforce

An owner must configure and verify these settings after pushing. The local auditor cannot inspect them.

- Protect the default/release branches or use rulesets: require PRs, required status checks, resolved review conversations and no force push/deletion. Restrict bypasses and record emergency use.
- Require the stable `standards-gate` check and relevant security checks. If a merge queue is enabled, require its run too.
- Require an independent reviewer and code-owner approval for sensitive paths when staffing permits; critical systems require independent approval. A solo project records the self-review arrangement rather than inventing a reviewer.
- Enable secret scanning and push protection where available; otherwise install an equivalent reviewed scanner in CI and before pushes. Check feature availability for the repository's plan and visibility.
- Enable dependency updates and vulnerability alerts where available; add source/code scanning suitable to the stack. Record any missing capability and the replacement control.
- Protect production environments and release tags; use least-privilege automation identities. Set CODEOWNERS to actual users/teams with the necessary access.

## Releases

Create an immutable version or revision, release notes, dependency inventory and artifact digest. Build once and promote the same tested artifact. Publish only after artifact installation/smoke tests; retain provenance and a software bill of materials for critical systems and redistributed deployable artifacts.

Use staged rollout, health verification and explicit rollback triggers for services. Test backward-compatible database changes with an expand/migrate/contract sequence where needed. A code rollback does not reverse an incompatible migration. Never make production releases depend on an unreviewed floating standards branch.

The supplied workflows verify code; they do not deploy. Secret scanning, hosted settings, production controls and product-specific integration/E2E tests must be completed during adoption.
