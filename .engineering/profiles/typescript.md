# JavaScript / TypeScript profile

Extends CODE-01/02, TEST-01/02 and BUILD-01.

- MUST declare a supported Node/runtime and package manager, commit the chosen lockfile and use a clean frozen install in CI. The starter uses npm and Node 24; browser projects also define browser support.
- SHOULD use TypeScript for new maintained application logic. MUST enable `strict`, run the compiler separately from tests, and justify `any`, non-null assertions, `@ts-ignore` and disabled rules locally. JavaScript repos use an equivalent static checking configuration or record a bounded migration plan.
- MUST use a formatter and lint configuration; starter uses Prettier and type-aware ESLint with unsafe/promise checks. Do not assume a bundler or test runner checks types.
- MUST validate external JSON, environment variables and API responses at runtime; TypeScript annotations disappear at runtime. Keep secrets server-side; browser environment variables and bundled source are public.
- MUST handle rejected promises, cancellation and expected errors; bound requests and retries. Avoid unchecked object/property access and string-built executable HTML/SQL/shell commands.
- MUST test user/domain behavior, asynchronous failures and relevant component/integration boundaries. Starter uses Vitest with branch/line/function/statement gates and includes all shipped source.
- MUST build and smoke-test packaged output; exported paths, ESM/CommonJS behavior and generated types must match the supported consumer contract. Keep application bundles and public library distribution rules separate.
- MUST review lifecycle/install scripts, audit dependencies and add appropriate source security analysis for deployed apps. `npm audit` does not provide complete source or secret scanning.

Evidence: `npm ci`, format/lint/type/test/build commands, dependency scan, artifact smoke test and runtime/platform matrix. Add Playwright or another browser tool for web journeys; the Node starter alone does not test a UI.
