# Merge verification — 2026-11-12

Candidate: https://github.com/Ballzatram/cltpolo/pull/23. Base revision: `45e0e0341a97a1c54135c9db8b24f7320e918d1c`.
Machine-readable evidence: [standards evidence](evidence/standards-2026-11-12.json).

All merges require a successful Engineering Standards workflow on the final PR head. The rollout also checks default-branch CI after merge. CI success is not a full policy-conformance or production-readiness certificate.

## Behavior and performance

The initial inventory compared 37 existing application/code/asset files using Git objects. Changes after that inventory are recorded below. This is file-preservation evidence, not a claim that all paths have been exercised.

## Generated updates under branch protection

Existing scheduled/manual generators retain their existing collection and validation rules. Publication now uses a unique automation branch and pull request, explicitly dispatches the required engineering workflow, then requests auto-merge after checks. This avoids direct default-branch writes and token-event recursion suppression. Four offline control-flow tests cover no-change, success, diff failure and commit failure. Actions default to read permissions; the existing update workflows alone request write scopes. Repository workflow PR creation and auto-merge are enabled. No workflow approves a review. If a concurrent base change makes an automation PR stale, its checks/update must be rerun before merge; protection is not bypassed. No live generator was manually triggered during verification.

## Hosted enforcement and limits

Required PR and strict GitHub Actions standards-gate, including administrators; no force push/deletion.

Public repositories require PRs, a strict up-to-date standards-gate owned by GitHub Actions, resolved review conversations and protections for administrators. No second reviewer is fabricated: the configured approval count is zero for this solo-owner account. CODEOWNERS remains an ownership signal, not a claim of independent approval. Protected deployment/recovery and product-specific manual evidence still require separate assessment.

This work does not certify production load capacity, game frame rate, live-provider performance, accessibility or recovery procedures. Remaining requirements are explicit in docs/audit.md; no waiver was invented.
