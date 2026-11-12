# Initial framework verification

Verified locally on 2026-11-11 using Windows, Python 3.14.5, uv 0.13.7, Node 24.22.3 and npm 11.19.1. This record covers the initial version 1.0.0 implementation; rerun checks after changes.

| Area | Observed result |
| --- | --- |
| Framework formatter, lint and strict types | Passed. |
| Framework regression tests | 55 passed; 86.50% combined source/branch coverage against an 80% gate. |
| Framework dependency audit | No known vulnerabilities reported by pip-audit. |
| Fresh Python starter | Locked install, format, lint, types and 6 behavior tests passed; sample source coverage 100%. |
| Python artifact | Source distribution and wheel built from the locked environment; wheel installed and its API exercised outside the source tree. |
| Python dependency audit | OSV audit passed with no known vulnerabilities; editable first-party sample skipped, third-party and dev dependencies scanned. |
| Fresh TypeScript starter | npm ci, formatting, type-aware lint, compiler checks, 6 behavior tests, build and isolated compiled-output smoke test passed; sample source coverage 100%. |
| TypeScript dependency audit | npm audit reported zero known vulnerabilities with the documented narrow lint-toolchain overrides. |
| Workflow validation | All three workflow files passed actionlint v1.7.12, obtained from the official release with its published checksum verified. |
| Structural checks | Framework and both generated starters passed structural prerequisites; each still requests manual assessment. |
| Documentation navigation | Relative links in the framework guide, docs and profiles resolved. |

The test suite includes malformed metadata, invalid profiles, expired/overlong waivers, unpinned actions, preservation of existing files and confirmation that target-manifest commands are not executed. Orchestration wrappers are exercised through actual generated-project runs rather than counted in unit coverage.

Initial advisory-service connection failures remained failures. A subsequent successful Python scan used OSV, now selected explicitly in the Python starter; no advisory was ignored to obtain a pass. The TypeScript scanner initially found a transitive minimatch advisory; the patched overrides are documented in the starter README and were validated through clean installation and all starter checks.

## Unverified or pending

- GitHub-hosted runs, branch protections, CODEOWNERS access, secret scanning/push protection and deployment settings: this repository has not been published or connected to remote enforcement.
- Python 3.12/3.13, Ubuntu and additional platform behavior: configured in CI, not executed locally. The Python jobs set UV_PYTHON and assert the actual runtime so the default development version cannot silently replace the matrix version.
- Product-specific acceptance, integration, accessibility, source-security, secret-history and operational reviews: these depend on the adopting project and remain required.
- Existing repositories: none have been audited or modified by this work.
- Full conformance: not claimed. The manual assessment in docs/audit.md remains pending.
