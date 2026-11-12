# Infrastructure, containers and platform

Extends CI-02, SEC-01/02, REL-01 and OPS-01.

- MUST keep declarative infrastructure versioned; format, validate, lint and security-check it. Review the actual plan/diff before applying consequential changes.
- MUST separate environments/accounts, constrain privileges and protect/encrypt state. Secrets must not enter committed plans, state copies or CI logs; plans can contain sensitive values.
- MUST pin providers/modules/tooling and release images appropriately; scan images and review base-image updates. Run containers as non-root where feasible and limit capabilities/resources.
- MUST use remote state locking or an equivalent safe coordination method for shared infrastructure. Define drift detection, break-glass access and reconciliation.
- MUST document deletion/replacement risks, recovery and data dependencies. Test backups/restores for managed data too; provider defaults are not evidence of recovery.
- MUST separate untrusted PR validation from privileged apply/deploy jobs. Protect production environments and apply only the reviewed revision/plan with appropriate artifact trust.
- MUST define observability, resource/cost limits and retirement/cleanup procedures.

Evidence: validation and scan results, reviewed plan, permission/state review, drift and recovery procedure. A syntax-valid configuration can still destroy data or expose a service.
