# Engineering standards adoption

Owner: Ballzatram. Policy: 1.0.0. Baseline source revision: `45e0e0341a97a1c54135c9db8b24f7320e918d1c`.

Static public site, investor/property models, Python property-research pipelines and Cloudflare workers. Research, donations and remote refresh are distinct trust boundaries; no live payments or data refresh are performed during standards checks.

## Verification

Run `uv run --project .engineering --locked python .engineering/tools/audit.py .` for structural prerequisites. Existing native test/build commands are retained in README and the workflows. `.github/workflows/engineering.yml` adds a consistent, read-only verification gate; it never deploys or uses production secrets. Review `docs/audit.md` for controls requiring manual evidence.

The command register includes existing syntax/compile checks where no full static type checker exists; these are not equivalent to strict typing. Legacy formatter/type/coverage gaps remain explicit, not silently waived. No approved exceptions have been invented. Source import/native platform requirements and hosted protections must be reviewed separately.

## Preservation

Default branches and deployed services are not changed by preparing this branch. Runtime source changes, if any, are limited to documented regression fixes and must pass the existing tests. Do not run live research, mail, payment, model generation, customer data changes or production deployment as a standards check.

## Recorded local verification

118 Node model/worker tests passed. The Python source/pipeline suite ran 73 cases with one existing skip. Browser results are recorded separately when available. Runtime code, property data, payment rules and remote-refresh behavior are unchanged. No live payment or refresh was executed.

See docs/audit.md for unresolved controls. A structural pass is not full conformance.

## Final candidate checks

See [merge verification](merge-verification.md) for current gates, commands and actual performance/coverage measurements. This supersedes the initial local-only/native-pending notes above. See .standards.json for the executable command register. Hosted feature restrictions and remaining conformance work remain explicit.
