# Working in Engineering Standards

Read README.md, docs/baseline.md and docs/ai-development.md before changes. Applicable language rules live in profiles/. This repository is itself governed by version 1.0.1.

- Preserve stable control IDs. Update VERSION, CHANGELOG.md and templates when policy changes; breaking requirements require a major version.
- Never label a structural check as full compliance. Keep pending evidence explicit.
- Do not run code from a target repo when auditing it. The auditor reads local metadata only and uses no network.
- The scaffolder must refuse nonempty destinations and never overwrite user work.
- Keep the framework snapshot and generated project instructions consistent.
- Validate with `uv run --locked python tools/check.py`; validate generated starters in isolated temporary directories after template changes.
- Never weaken checks, coverage or policy to make generated projects pass. Report unrun checks honestly.
- Use no production credentials or personal data. Do not publish or deploy as part of an audit.
