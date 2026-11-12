# Security and dependencies

## Design and implementation

Identify trust boundaries, exposed surfaces, privileged operations and data flows. Critical systems need a written threat model; other projects need a short review of their meaningful risks. Apply a selected, versioned OWASP ASVS checklist to relevant web/API systems without treating this baseline as ASVS certification.

Validate size, shape and semantics of external input. Use parameterized queries, safe serialization, context-aware output encoding and platform cryptography. Never invent authentication, encryption or password hashing. Enforce authorization for each protected operation and resource, including tenant boundaries. Test denial cases, not just successful login.

Bound file paths, uploads, redirects, outbound network targets, request sizes and resource consumption. Treat fetched URLs and uploaded content as untrusted. Apply appropriate CSRF, CORS, session/cookie and rate-limit controls; permissive CORS is not authorization. Avoid sensitive details in errors, telemetry, URLs and analytics.

## Dependencies and supply chain

Keep direct dependencies minimal and purposeful. Review publisher/project identity, license, maintenance, transitive risk and installation hooks. Verify unfamiliar packages and APIs before adding them; do not install a name simply because a model suggested it.

Commit application and development lockfiles; make CI fail on lock/manifest drift. Library release metadata normally uses compatible ranges, with locked development tools and separate supported-range tests. Pin containers by digest for release; refresh and scan base images deliberately. Record license obligations before distribution; use an SBOM for the release artifacts specified in CI/CD policy.

Run dependency scans on PRs, protected-branch changes and at least weekly while maintained. Run relevant source/static analysis and secret scanning too. A successful vulnerability lookup only means no matching known advisory was reported for the scanned inputs.

Policy response targets: actively exploited or exposed critical findings are triaged immediately and mitigated within 24 hours; other critical findings within 72 hours; high within 7 days; medium within 30 days; low within 90 days. These are internal targets, measured from discovery. Record exploitability, affected paths, owner and decision. Unknown severity fails triage until assessed. Expired exceptions block acceptance. Scanner/service failure must be visible.

## Secrets and data

Use managed secret storage or local environment injection; commit a redacted `.env.example` only. Test fixtures must use clearly fake credentials. Scan tracked files and relevant history before first publication and configure ongoing scanning/push protection. Root ignore rules do not remove already-tracked secrets.

Collect only necessary data. Define classification, access, retention, deletion and encryption appropriate to the deployment. Use synthetic/redacted test data and scrub logs. Maintain a private vulnerability route and a credential rotation procedure. Critical/security incidents need containment, impact assessment, recovery and a short follow-up with preventive action.
