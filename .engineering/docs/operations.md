# Operations, data and performance

Apply these requirements to deployed systems; mark the relevant controls N/A with rationale for a purely local tool that has no service or persistent data.

- Name the service owner and responder. Document environments, configuration, dependencies, deployment and rollback commands. A runbook must be usable without the original developer present.
- Expose readiness and liveness appropriate to the system. Distinguish a healthy process from a system able to serve requests; avoid restart loops caused by overly broad liveness checks.
- Use structured logs, correlation IDs and useful error context. Define metrics for traffic, errors, latency and saturation. Do not log secrets or sensitive content. Avoid unbounded metric labels.
- Set realistic availability/latency objectives, alert on actionable symptoms and exercise an alert. Document diagnostic steps and an escalation/contact route.
- Time out outbound work; bound retries with backoff/jitter and retry only safe/idempotent operations. Bound queues and concurrency; handle cancellation and graceful shutdown. Define duplicate delivery and partial failure behavior.
- Set resource and cost budgets, pagination/size limits and expected workload. Measure representative performance before claiming scale; test bottlenecks proportionate to impact.
- Version schema changes; test upgrades from supported prior states, failure handling and rollback/forward recovery. Use transactions and integrity constraints where needed. Define timezone and money precision explicitly.
- Encrypt and restrict backups, set retention plus recovery point/time objectives, and rehearse restore into an isolated environment. Record the date and observed recovery time. Test recovery after destructive or incompatible migrations.
- Maintain lifecycle and retirement guidance: revoke credentials, remove infrastructure, resolve data retention and notify affected users where applicable.

Use the [runbook template](../templates/common/docs/runbook.md) as the minimum operational record. Critical systems require representative failure/restore exercises before release and after material changes.
