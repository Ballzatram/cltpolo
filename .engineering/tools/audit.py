"""Read-only structural prerequisites audit. Never execute target code or use the network."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Literal

FRAMEWORK_VERSION = "1.0.0"
CONTROLS = frozenset(
    [
        "GOV-01",
        "GOV-02",
        "REPO-01",
        "REPO-02",
        "ARCH-01",
        "ARCH-02",
        "CODE-01",
        "CODE-02",
        "TEST-01",
        "TEST-02",
        "BUILD-01",
        "CI-01",
        "CI-02",
        "SEC-01",
        "SEC-02",
        "SEC-03",
        "DOC-01",
        "REL-01",
        "OPS-01",
        "DATA-01",
        "UX-01",
        "AI-01",
    ]
)
PROFILES = frozenset(
    [
        "python",
        "typescript",
        "other-languages",
        "web",
        "services",
        "libraries",
        "cli",
        "data-ml",
        "infrastructure",
        "mobile-desktop",
    ]
)
REQUIRED_FILES = (
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".gitignore",
    ".editorconfig",
    "docs/architecture.md",
    "docs/audit.md",
    "docs/waivers.json",
)
COMMANDS = frozenset(("format", "lint", "types", "test", "build", "security"))


@dataclass(frozen=True)
class Finding:
    """One prerequisite finding, deliberately distinct from a compliance decision."""

    check: str
    status: Literal["pass", "fail", "review"]
    detail: str


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(root: Path, *, today: date | None = None) -> list[Finding]:
    """Inspect only metadata/files; zero failures means structural readiness only."""
    root = root.resolve()
    today = today or date.today()
    findings: list[Finding] = []
    declared_test_dirs: list[Path] = []
    specification_only = False

    def result(check: str, passed: bool, detail: str) -> None:
        findings.append(Finding(check, "pass" if passed else "fail", detail))

    if not root.is_dir():
        return [Finding("repository", "fail", f"Not a directory: {root}")]

    for filename in REQUIRED_FILES:
        path = root / filename
        result(
            f"file:{filename}",
            path.is_file() and path.stat().st_size > 0,
            f"Required nonempty file: {filename}",
        )

    manifest: object = None
    try:
        manifest = _read_json(root / ".standards.json")
    except (OSError, ValueError) as exc:
        result("manifest", False, f"Cannot read .standards.json: {exc}")
    if not isinstance(manifest, dict):
        result("manifest:object", False, "Manifest must be a JSON object.")
    else:
        kind = manifest.get("repository_kind", "code")
        result(
            "repository-kind",
            kind in ("code", "specification"),
            "Declare code or specification repository kind.",
        )
        specification_only = kind == "specification"
        directories = manifest.get("test_directories", [])
        if not isinstance(directories, list):
            result("test-directories", False, "test_directories must be an array.")
        else:
            for index, relative in enumerate(directories):
                valid = isinstance(relative, str) and bool(relative.strip())
                directory = (root / relative).resolve() if valid else root.parent
                valid = valid and directory.is_relative_to(root) and directory.is_dir()
                result(
                    f"test-directory:{index}",
                    valid,
                    "Declared test directory must exist inside the repository.",
                )
                if valid:
                    declared_test_dirs.append(directory)
        result(
            "schema",
            type(manifest.get("schema_version")) is int
            and manifest["schema_version"] == 1,
            "Supported schema_version is 1.",
        )
        result(
            "version",
            manifest.get("framework_version") == FRAMEWORK_VERSION,
            f"This auditor evaluates framework {FRAMEWORK_VERSION} only.",
        )
        result("owner", _nonempty(manifest.get("owner")), "A named owner is required.")
        result(
            "risk",
            manifest.get("risk_tier") in ("local", "standard", "critical"),
            "Choose local, standard or critical risk.",
        )
        result(
            "lifecycle",
            manifest.get("lifecycle")
            in ("prototype", "active", "maintenance", "archived"),
            "Declare lifecycle status.",
        )
        profiles = manifest.get("profiles")
        valid_profiles = (
            isinstance(profiles, list)
            and bool(profiles)
            and all(isinstance(item, str) and item in PROFILES for item in profiles)
            and len(profiles) == len(set(profiles))
        )
        result("profiles", valid_profiles, "Select unique supported profiles.")
        commands = manifest.get("commands")
        result(
            "commands",
            isinstance(commands, dict)
            and all(_nonempty(commands.get(command)) for command in COMMANDS),
            "Declare format, lint, types, test, build and security commands; not executed.",
        )
        source = manifest.get("framework_source")
        source_ok = False
        if isinstance(source, str) and source.strip():
            snapshot = (root / source).resolve()
            if snapshot.is_relative_to(root):
                try:
                    source_ok = (
                        (snapshot / "VERSION").read_text(encoding="utf-8").strip()
                        == FRAMEWORK_VERSION
                        and (snapshot / "docs/baseline.md").is_file()
                        and (snapshot / "profiles/README.md").is_file()
                    )
                except OSError:
                    source_ok = False
        result(
            "snapshot",
            source_ok,
            "framework_source must point to an in-repo versioned policy snapshot.",
        )
        component_profiles: set[str] = set()
        components = manifest.get("components", [])
        if not isinstance(components, list):
            result("components", False, "Components must be a JSON array.")
        else:
            for index, component in enumerate(components):
                label = f"component:{index}"
                if not isinstance(component, dict) or not all(
                    _nonempty(component.get(field))
                    for field in ("path", "profile", "dependency_manifest", "lockfile")
                ):
                    result(
                        label,
                        False,
                        "Each component needs path, profile, dependency_manifest and lockfile.",
                    )
                    continue
                profile = component["profile"]
                if (
                    profile not in PROFILES
                    or not valid_profiles
                    or not isinstance(profiles, list)
                    or profile not in profiles
                ):
                    result(
                        label,
                        False,
                        "Component profile must be selected by the repository.",
                    )
                    continue
                directory = (root / component["path"]).resolve()
                contained = directory.is_relative_to(root)
                result(
                    f"{label}:path",
                    contained and directory.is_dir(),
                    "Component must be inside the repository.",
                )
                if not contained:
                    continue
                component_profiles.add(profile)
                for field in ("dependency_manifest", "lockfile"):
                    target = (directory / component[field]).resolve()
                    result(
                        f"{label}:{field}",
                        target.is_relative_to(directory) and target.is_file(),
                        f"Declared component {field} must exist inside its component.",
                    )
        if valid_profiles and isinstance(profiles, list):
            if "python" in profiles and "python" not in component_profiles:
                for filename in ("pyproject.toml", "uv.lock"):
                    result(
                        f"python:{filename}",
                        (root / filename).is_file(),
                        f"Default Python profile prerequisite: {filename}; review equivalents.",
                    )
            if "typescript" in profiles and "typescript" not in component_profiles:
                for filename in ("package.json", "package-lock.json", "tsconfig.json"):
                    result(
                        f"typescript:{filename}",
                        (root / filename).is_file(),
                        f"Default npm/TypeScript prerequisite: {filename}; review equivalents.",
                    )
    test_dirs = [root / "tests", root / "test", root / "__tests__", *declared_test_dirs]
    if specification_only:
        findings.append(
            Finding(
                "tests",
                "review",
                "Specification-only repository: no runtime behavior has been verified. Confirm source state and applicability manually.",
            )
        )
    else:
        result(
            "tests",
            any(path.is_dir() and any(path.rglob("*.*")) for path in test_dirs),
            "A test directory containing files is required; assertion quality needs review.",
        )
    workflows = root / ".github/workflows"
    workflow_files = sorted((*workflows.glob("*.yml"), *workflows.glob("*.yaml")))
    result(
        "ci",
        bool(workflow_files),
        "Default host prerequisite: GitHub Actions; review equivalents.",
    )
    result(
        "ownership",
        (root / ".github/CODEOWNERS").is_file(),
        "Default host prerequisite: CODEOWNERS; actual access requires review.",
    )
    for path in workflow_files:
        content = path.read_text(encoding="utf-8")
        for reference in re.findall(r"\buses:\s*['\"]?([^\s'\"#]+)", content):
            if reference.startswith("./"):
                continue
            pinned = bool(re.fullmatch(r"[^@]+@[0-9a-fA-F]{40}", reference))
            # Image actions use an OCI digest rather than a Git commit.
            pinned = pinned or bool(
                re.fullmatch(r"docker://.+@sha256:[0-9a-fA-F]{64}", reference)
            )
            result(
                f"action-pin:{path.name}:{reference}",
                pinned,
                "External action must use a full commit SHA or container SHA256 digest.",
            )

    try:
        waivers = _read_json(root / "docs/waivers.json")
        if not isinstance(waivers, list):
            result("waivers", False, "Waivers must be a JSON array.")
        else:
            for index, waiver in enumerate(waivers):
                label = f"waiver:{index}"
                fields = (
                    "control",
                    "reason",
                    "owner",
                    "approved_by",
                    "expires",
                    "mitigation",
                    "tracking",
                )
                if not isinstance(waiver, dict) or not all(
                    _nonempty(waiver.get(field)) for field in fields
                ):
                    result(
                        label, False, "Every waiver field must be a nonempty string."
                    )
                    continue
                result(
                    f"{label}:control",
                    waiver["control"] in CONTROLS,
                    "Waiver must reference a known baseline control.",
                )
                try:
                    expiry = date.fromisoformat(waiver["expires"])
                    valid = 0 < (expiry - today).days <= 90
                except (TypeError, ValueError):
                    valid = False
                result(
                    f"{label}:expiry",
                    valid,
                    "Waiver expiry must be after today and no more than 90 days ahead.",
                )
    except (OSError, ValueError) as exc:
        result("waivers", False, f"Cannot read waiver registry: {exc}")
    findings.append(
        Finding(
            "manual-assessment",
            "review",
            "Review every control/profile, evidence, hosted settings, "
            "behavior, security and waiver approval in docs/audit.md.",
        )
    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        findings = audit(args.repository)
    except (OSError, UnicodeError, ValueError) as exc:
        findings = [Finding("read-error", "fail", str(exc))]
    failed = any(item.status == "fail" for item in findings)
    if args.as_json:
        print(
            json.dumps(
                {
                    "framework_version": FRAMEWORK_VERSION,
                    "structural_pass": not failed,
                    "full_conformance": "not-assessed",
                    "findings": [asdict(item) for item in findings],
                },
                indent=2,
            )
        )
    else:
        for item in findings:
            print(f"{item.status.upper():6} {item.check}: {item.detail}")
        print(
            "\nSTRUCTURAL "
            + ("FAIL" if failed else "PASS")
            + " — full conformance is not assessed; manual review is required."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
