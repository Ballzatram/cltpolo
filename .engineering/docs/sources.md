# Source register

Reviewed 2026-11-11. These sources inform the framework; the controls, internal tiers, coverage thresholds, response times and waiver rules are our own policy decisions. This is not an exhaustive control mapping or a compliance attestation.

| Source | Used for |
| --- | --- |
| [NIST SSDF, SP 800-218 v1.1](https://csrc.nist.gov/pubs/sp/800/218/final) | Security practices across development, protection, production and vulnerability response. |
| [OWASP ASVS](https://asvs.owasp.org/) | Selecting verifiable web/application security requirements. |
| [GitHub secure use reference](https://docs.github.com/en/actions/reference/security/secure-use) | Action SHA pins, workflow trust boundaries and scoped credentials. |
| [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) | Required checks/reviews and hosted enforcement. |
| [Python PEP 8](https://peps.python.org/pep-0008/) | Python naming and code conventions; formatter configuration resolves mechanical choices. |
| [Python Packaging: src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) | Import/package separation and installation testing. |
| [pytest good integration practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html) | Isolated environments and test/import layout. |
| [Ruff configuration](https://docs.astral.sh/ruff/configuration/) | Shared lint and formatting configuration. |
| [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/) | `--locked` checks freshness; `--frozen` alone skips that validation. |
| [uv GitHub Actions integration](https://docs.astral.sh/uv/guides/integration/github/) | Explicit uv setup and locked CI installs. |
| [TypeScript strict](https://www.typescriptlang.org/tsconfig/strict.html) | Strict type checking defaults. |
| [npm ci](https://docs.npmjs.com/cli/v11/commands/npm-ci/) | Lockfile-based clean installs. |
| [Playwright best practices](https://playwright.dev/docs/best-practices) | Observable behavior and isolated browser tests. |
| [WCAG 2.2](https://www.w3.org/TR/WCAG22/) | Accessibility acceptance for web interfaces. |

Verify references and tool pins during framework upgrades. No vendor, hosting provider or payment service is required by this framework; equivalent tools can satisfy the same evidence requirements.
