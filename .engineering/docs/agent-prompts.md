# Repeatable adoption requests

These prompts help start work; they do not replace the policies or required checks. Fill in paths and product context. A repository's own more specific instructions and authorized task scope still apply.

## New project

```text
Build this project using Engineering Standards version 1.0.1 at <local path or
immutable canonical reference>. Read the universal baseline and select every
applicable language/product profile. Record owner, lifecycle, risk and version
in .standards.json, and vendor the exact policy snapshot in .engineering/.

First state acceptance examples and material risks. Use the existing language
starter where applicable. Implement the product with meaningful behavior and
failure-path tests, strict checks, locked installs, artifact verification and
required CI gates. Complete the audit with actual evidence. Keep remote settings,
deployment checks and unverified requirements pending until inspected.

Report changed behavior, checks actually run, outstanding gaps and any waivers.
Do not claim conformance from a structural pass alone.
```

## Existing repository

```text
Assess this repository against Engineering Standards version 1.0.1 at <path>.
Inventory its languages, product types, data, deployment, ownership and risks.
Run the read-only structural audit; inspect behavior, tests, pipeline trust,
dependency/secret/source scanning, artifact build and relevant operations.

Complete a control-by-control assessment with current evidence, applicable
profile requirements, justified N/A items and explicit pending reviews. Produce
a remediation backlog with control ID, concrete gap, risk, owner and verification.
Preserve existing working tools when they meet the same requirements. Do not
overwrite project configuration or execute unknown audit-target commands blindly.

Implement the authorized remediation in focused changes, prioritizing exposed
secrets, exploitable paths, data loss and missing checks. Verify each change;
do not weaken gates. Report conforming, conforming-with-waivers or not-conforming
with evidence and remaining limitations.
```
