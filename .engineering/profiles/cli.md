# CLI and automation profile

Extends CODE-02, TEST-01, REPO-01 and REL-01.

- MUST document commands, arguments, config precedence and exit codes. Send machine-readable output/results to stdout and diagnostics to stderr when relevant.
- MUST return nonzero on failure, handle interrupted work and avoid leaking secrets in arguments/logs. Quote subprocess arguments safely and avoid a shell when it is unnecessary.
- MUST validate destinations and scope before destructive filesystem or remote actions. Provide preview/dry-run or explicit confirmation for consequential operations as appropriate to the workflow.
- MUST define repeat/idempotent behavior for automation, partial failure and restart/resume. Use atomic writes for important outputs where feasible.
- MUST test successful use, invalid arguments, missing config, denied access, partial failures and relevant Windows/POSIX path behavior. Test installation/entry points outside the repository.
- SHOULD offer `--help`, `--version`, predictable noninteractive usage and structured output when consumed by scripts.

Evidence: process-level tests with real exit codes and isolated files, documented operational limitations and installation smoke tests.
