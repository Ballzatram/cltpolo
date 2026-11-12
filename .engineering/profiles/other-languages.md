# Other language ecosystems

The universal baseline remains mandatory. Choose native tools and document exact local/CI commands rather than applying Python conventions to another language.

| Ecosystem | Required equivalents to select and configure |
| --- | --- |
| Go | gofmt, go vet/static analysis, go test and race checks where concurrent, module checksums, govulncheck, supported Go versions |
| Rust | rustfmt, Clippy, cargo test, lockfile policy, dependency advisory checks, unsafe-code justification |
| Java/Kotlin | formatter, compiler/static analysis, JUnit or equivalent, pinned Maven/Gradle wrapper, dependency locking/verification and vulnerability checks |
| .NET | dotnet format/analyzers, nullable checks, dotnet test/coverage, reproducible restore, package audit and SDK selection |
| C/C++ | clang-format/static analysis, compiler warnings, sanitizers where feasible, native tests, explicit toolchain/dependency management |
| Swift / Objective-C | formatter/lint/static analysis, native tests, dependency resolution, supported platform matrix |
| Ruby / PHP / others | ecosystem formatter, static/type checks as applicable, behavior tests, locked development/runtime dependencies and security scans |

MUST provide supported toolchain versions, deterministic installs, tests, source/dependency checks and artifact verification. These are capability requirements, not an assertion that merely invoking a named tool proves safety. Review the current official ecosystem documentation when implementing a profile. Add a tested language starter through a framework change before advertising one as ready.
