# **PROJECT_NAME**

Owner: **OWNER**. Status: prototype; standards review pending.

Replace this introduction with purpose, users, non-goals and usage. The label-normalization function is a tested example, not completed product functionality. Complete architecture, operational and audit records before release.

## Setup and checks

Use the exact Node version in `.node-version`, which includes npm. This project supports Node 24. Review toolchain updates as a unit, and regenerate the lockfile deliberately if dependencies change.

```text
npm ci
npm run format:check
npm run lint
npm run typecheck
npm test
npm run security
npm run build
npm run smoke
python .engineering/tools/audit.py .
```

Use `npm run format` to format locally. CI runs on Linux and Windows. The starter is Node-only; add the web/UI profile, browser support, accessibility checks and component/E2E tests if building a website.

The lockfile uses narrow `minimatch` overrides for the lint toolchain to address [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249). These cross a dependency major version, so lint/configuration behavior must be rechecked during upgrades. Remove them once upstream dependencies resolve to patched versions without overrides; do not suppress the advisory or force an unsupported linter downgrade.

## Standards and release

`.standards.json` pins the framework to the bundled `.engineering/` snapshot. Add applicable product profiles and select the right risk tier; language-only/local is provisional. A structural pass does not complete the manual review in `docs/audit.md`.

Before release: replace documentation prompts, select license/distribution terms, configure real ownership and hosted protection/security settings, add secret and source-security scanning, and complete the control/profile review. npm audit scans known dependency advisories only. This private starter does not publish or deploy. A future library needs package metadata, exports, consumer installation tests and an explicit release workflow.
