# Local verification prerequisites

Use Python 3.12 or newer, the project's declared Node version, uv 0.13.7 and Gitleaks **8.30.1**. Application dependencies and the vendored policy's development dependencies are separate environments. The auditor uses PyYAML from the policy lockfile; it is not an application runtime dependency.

From a consumer repository, run:

```text
uv run --project .engineering --locked python .engineering/tools/audit.py .
uv run --directory .engineering --locked --python 3.12 python tools/check.py
```

The second command checks the policy implementation itself. Follow the application's README and .standards.json for application checks. Explicit unavailable/N/A records are status records, not executable commands or passing checks.

## Install and verify Gitleaks

Download the exact archive for your platform from [Gitleaks v8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1). Check its SHA256 before extracting it into a user-controlled tool directory and adding that directory to PATH. Keep downloaded binaries outside tracked application files. Do not substitute the latest release.

| Platform | Archive | SHA256 |
| --- | --- | --- |
| Windows x64 | gitleaks_8.30.1_windows_x64.zip | d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e |
| Linux x64 | gitleaks_8.30.1_linux_x64.tar.gz | 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb |
| macOS Apple Silicon | gitleaks_8.30.1_darwin_arm64.tar.gz | b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5 |
| macOS Intel | gitleaks_8.30.1_darwin_x64.tar.gz | dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709 |

These digests were checked against the official release metadata. For other architectures use that release's matching archive and checksums file.

On Windows, use `Get-FileHash -Algorithm SHA256 -LiteralPath PATH_TO_ARCHIVE` and then `Expand-Archive`. On Linux, use `sha256sum PATH_TO_ARCHIVE` and then `tar -xzf PATH_TO_ARCHIVE`. On macOS, use `shasum -a 256 PATH_TO_ARCHIVE` and then `tar -xzf PATH_TO_ARCHIVE`. Extract only after the hash matches. Add the extracted binary's directory to PATH.

Run `gitleaks version`: it must print `8.30.1`. The wrapper also enforces the version and fails when the binary is missing or differs.

Fetch the default branch before local scanning so `origin/HEAD` identifies the reviewed policy. Run `python .engineering/tools/secret_scan.py`. You can pass an explicit immutable `--trusted-revision` and `--scanner /path/to/gitleaks`. CI supplies both explicitly, pins reviewed initial-adoption bootstrap inputs, and verifies checksums of committed Git bytes independently of working-copy line endings. Rules and fingerprints are materialized outside the candidate checkout; candidate inline allow comments are disabled.

The root framework uses `uv run --locked python tools/audit.py TARGET` and `python tools/secret_scan.py` from its own checkout.
