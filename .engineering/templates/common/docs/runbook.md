# Runbook

Status: draft. For a local non-deployed tool, record which operational sections are not applicable and why.

| Item                        | Project-specific procedure                                               |
| --------------------------- | ------------------------------------------------------------------------ |
| Owner / escalation          | Set actual owner and contact route.                                      |
| Environments / dependencies | Identify accounts, systems and configuration sources.                    |
| Deploy / release            | Commands, trusted artifact/revision and approvals.                       |
| Health and objectives       | Readiness, error/latency targets and how to verify them.                 |
| Diagnostics / alerts        | Dashboard/log locations, actionable alerts and exercised test.           |
| Rollback / recovery         | Commands, triggers and data/schema limitations.                          |
| Backup / restore            | Retention, RPO/RTO, restricted storage and last restore evidence.        |
| Security incidents          | Containment, credential rotation, impact assessment and reporting.       |
| Data / privacy              | Classification, access, retention, deletion and log redaction.           |
| Performance / cost          | Expected workload, resource/cost limits and representative measurements. |
| Retirement                  | Data handling, credential revocation and resource cleanup.               |
