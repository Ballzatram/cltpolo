# Python profile

Extends CODE-01/02, TEST-01/02 and BUILD-01.

- MUST declare a supported Python range in `pyproject.toml`; use a project-local virtual environment and a committed dev/application lockfile. The starter targets Python 3.12–3.14; change metadata and the CI matrix together when support changes.
- MUST use PEP 8 naming, four-space indentation and a single formatter. Starter defaults: Ruff formatter, 88 columns, sorted imports, common correctness/modernization rules and selected security rules. Do not layer competing formatters.
- MUST type public functions and module boundaries and run a type checker. Starter uses strict mypy. Any/ignores need a local rationale; do not blanket-ignore an entire module's errors.
- SHOULD use `src/<package>/` for installable code. The framework tools themselves use an intentional scripts layout. Do not modify `sys.path` to conceal broken packaging.
- MUST separate pure domain logic from I/O. Prefer explicit dependencies, context managers, `pathlib`, aware datetimes and decimal/integer money units where relevant. Avoid mutable defaults, wildcard imports, import-time network/file writes and broad swallowed exceptions.
- MUST validate configuration on startup, bound network calls, log context without secrets and preserve exception causes where useful. Use domain-specific errors at boundaries.
- MUST test with pytest (or a justified equivalent), isolate fixtures and use strict marker/config checking. New starters use importlib imports and branch coverage including unexecuted source.
- MUST build and install the wheel outside the source tree before publishing. Test all claimed runtimes and supported OS-specific behavior. Do not use editable installs as the sole proof of correct distribution.
- MUST audit runtime and dev dependencies and review lock changes. Pin build tooling for application builds; keep public library dependency metadata appropriately compatible.

Evidence: clean locked sync, Ruff, mypy, pytest/coverage, dependency audit, wheel build and isolated-install smoke test, runtime matrix, and a code review of error/resource boundaries. These checks do not replace service, data or UI profile requirements.
