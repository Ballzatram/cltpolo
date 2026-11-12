# Mobile and desktop applications

Extends UX-01, SEC-03, TEST-01/02 and REL-01.

- MUST define supported OS/device versions and test installation, upgrade, uninstall, accessibility and critical user journeys.
- MUST request least-necessary permissions, store credentials in platform-secure storage, protect local data and redact logs/crash reports.
- MUST test lifecycle/background transitions, interrupted network operations, offline behavior and sync/conflict handling where relevant.
- MUST review update/signing mechanisms, protect signing credentials, and verify signed distributable artifacts and recovery/rollback constraints.
- MUST document release/store requirements, privacy disclosures, telemetry and platform-specific behavior. Verify current platform policies during release preparation.
- Desktop apps with web runtimes MUST constrain privileged bridges and treat rendered/network content as untrusted. Do not expose filesystem or shell authority to arbitrary page content.

Evidence: representative device/OS tests, package upgrade smoke test, permission review, accessibility review and signed-release verification.
