# Framework architecture

This repository defines a versioned engineering policy and supplies optional implementation tooling. Policies in `docs/` apply across stacks; `profiles/` add language/product requirements. `templates/common/` holds project records and guidance, while Python and TypeScript directories add runnable language configurations.

`tools/audit.py` reads a target's metadata, required files and action references. It does not import or execute the target, run its declared commands, make network requests, evaluate test assertions or inspect hosted settings. Findings distinguish structural prerequisites from manual review. Default structural checks assume uv/Python or npm/TypeScript and GitHub; alternate tooling requires an explicit reviewer mapping and may still produce structural findings.

`tools/scaffold.py` creates projects outside this repository, refuses nonempty destinations and copies a pinned policy snapshot. Template code is an intentionally small example. No production system, deployment account or customer data is involved. The scaffolder performs local file writes only; interrupted generation can leave a partial directory, which must be inspected before retrying. It is intended for a single writer, not concurrent writers to the same destination.

The policy has stable IDs. A consumer's manifest records its exact version, selected profiles, owner, lifecycle and risk. An audit record assesses each control with evidence; a waiver registry records bounded exceptions. Structural readiness cannot be used as an attestation of security or correctness.

Tool dependencies are locked, source/static checks run locally and in the provided workflow, and regression tests exercise malformed inputs, nonexecution, no-overwrite behavior and generated-project consistency. Remote enforcement, approval identities and production readiness remain explicit review responsibilities.
