# Libraries and SDKs

Extends ARCH-02, BUILD-01, DOC-01 and REL-01.

- MUST define public API, supported runtimes/platforms, versioning, deprecation and compatibility policy. Internal symbols must not accidentally become a promised API.
- MUST test public behavior and a supported dependency/runtime range. Locked dev dependencies do not prove broad compatibility.
- MUST build, install and import/use the distributable outside the source checkout. Check included files, type information, metadata, license/notice obligations and exported entry points.
- MUST document examples, configuration, errors and migration paths for breaking changes; validate representative examples.
- MUST publish from a reviewed immutable revision using scoped/short-lived publishing credentials where supported. Retain artifact integrity/provenance evidence appropriate to risk.
- SHOULD keep dependencies minimal and avoid unnecessary restrictive runtime pins in public package metadata.

Evidence: package contents, isolated consumer smoke test, compatibility runs and reviewed release notes.
