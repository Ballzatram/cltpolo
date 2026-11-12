from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from datetime import date, timedelta
from pathlib import Path

import pytest

# Process tests invoke only this repository's scripts with argument arrays.
from tools.audit import CONTROLS, FRAMEWORK_VERSION, audit
from tools.scaffold import create_project

TODAY = date(2026, 11, 11)
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return create_project(tmp_path / "sample-project", "python", "devin")


def failures(project: Path) -> set[str]:
    return {item.check for item in audit(project, today=TODAY) if item.status == "fail"}


def write_manifest(project: Path, **updates: object) -> None:
    path = project / ".standards.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document.update(updates)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_starter_is_structurally_ready_but_requires_manual_review(
    project: Path,
) -> None:
    assert failures(project) == set()
    assert any(item.status == "review" for item in audit(project))
    assert "pending" in (project / "docs/audit.md").read_text()


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_scaffold_has_local_versioned_standards(tmp_path: Path, language: str) -> None:
    project = create_project(tmp_path / "sample", language, "org/team")
    assert not failures(project)
    assert (project / ".engineering/VERSION").read_text().strip() == FRAMEWORK_VERSION
    assert "@org/team" in (project / ".github/CODEOWNERS").read_text()


@pytest.mark.parametrize(
    ("key", "value", "check"),
    [
        ("schema_version", 2, "schema"),
        ("schema_version", True, "schema"),
        ("framework_version", "999.0.0", "version"),
        ("owner", " ", "owner"),
        ("risk_tier", "unknown", "risk"),
        ("lifecycle", None, "lifecycle"),
        ("profiles", [], "profiles"),
        ("profiles", ["python", "python"], "profiles"),
        ("profiles", [{"python": True}], "profiles"),
        ("profiles", ["unknown"], "profiles"),
        ("commands", {}, "commands"),
        ("commands", None, "commands"),
        ("framework_source", "https://example.invalid", "snapshot"),
        ("framework_source", "..", "snapshot"),
        ("framework_source", None, "snapshot"),
    ],
)
def test_rejects_invalid_manifest_fields(
    project: Path, key: str, value: object, check: str
) -> None:
    write_manifest(project, **{key: value})
    assert check in failures(project)


@pytest.mark.parametrize("content", ["[]", "null", "{malformed"])
def test_malformed_manifest_fails_without_execution(
    project: Path, content: str
) -> None:
    (project / ".standards.json").write_text(content)
    assert "manifest:object" in failures(project)


def test_missing_and_empty_prerequisites_fail(project: Path) -> None:
    (project / "README.md").write_text("")
    (project / "pyproject.toml").unlink()
    (project / ".engineering/VERSION").unlink()
    assert {"file:README.md", "python:pyproject.toml", "snapshot"} <= failures(project)


def test_missing_repository_returns_failure(tmp_path: Path) -> None:
    assert failures(tmp_path / "absent") == {"repository"}


def test_commands_in_manifest_are_never_executed(project: Path) -> None:
    marker = project / "must-not-exist"
    write_manifest(
        project,
        commands={
            key: f"touch {marker}"
            for key in ("format", "lint", "types", "test", "build", "security")
        },
    )
    audit(project)
    assert not marker.exists()


@pytest.mark.parametrize(
    "reference", ["actions/checkout@v7", "org/repo@main", "org/repo"]
)
def test_floating_action_references_fail(project: Path, reference: str) -> None:
    workflow = project / ".github/workflows/unpinned.yml"
    workflow.write_text(f"jobs:\n  test:\n    steps:\n      - uses: {reference}\n")
    assert any(
        "unpinned.yml" in check and check.startswith("action-pin:")
        for check in failures(project)
    )


def test_local_and_digest_pinned_actions_are_accepted(project: Path) -> None:
    (project / ".github/workflows/pins.yml").write_text(
        "jobs:\n  test:\n    steps:\n      - uses: ./local/action\n      - uses: docker://image@sha256:"
        + "a" * 64
    )
    (project / "local/action").mkdir(parents=True)
    (project / "local/action/action.yml").write_text(
        "runs:\n  using: composite\n  steps: []\n"
    )
    assert not failures(project)


def valid_waiver() -> dict[str, str]:
    return {
        "control": "TEST-02",
        "reason": "Measured legacy gap",
        "owner": "devin",
        "approved_by": "reviewer",
        "expires": (TODAY + timedelta(days=30)).isoformat(),
        "mitigation": "Critical paths covered",
        "tracking": "issue-42",
    }


@pytest.mark.parametrize("days", [-1, 0, 91])
def test_expired_and_unbounded_waivers_fail(project: Path, days: int) -> None:
    waiver = valid_waiver()
    waiver["expires"] = (TODAY + timedelta(days=days)).isoformat()
    (project / "docs/waivers.json").write_text(json.dumps([waiver]))
    assert "waiver:0:expiry" in failures(project)


@pytest.mark.parametrize(
    "content", ["{}", "null", "not-json", "[null]", '[{"control":"TEST-02"}]']
)
def test_invalid_waiver_registry_fails(project: Path, content: str) -> None:
    (project / "docs/waivers.json").write_text(content)
    assert any(check.startswith("waiver") for check in failures(project))


def test_valid_waiver_never_hides_missing_requirements(project: Path) -> None:
    (project / "docs/waivers.json").write_text(json.dumps([valid_waiver()]))
    (project / "README.md").unlink()
    assert "file:README.md" in failures(project)
    assert not any(check.startswith("waiver") for check in failures(project))


@pytest.mark.parametrize(
    ("field", "value", "check"),
    [
        ("control", "UNKNOWN-99", "waiver:0:control"),
        ("expires", "invalid-date", "waiver:0:expiry"),
    ],
)
def test_invalid_waiver_details_fail(
    project: Path, field: str, value: str, check: str
) -> None:
    waiver = valid_waiver()
    waiver[field] = value
    (project / "docs/waivers.json").write_text(json.dumps([waiver]))
    assert check in failures(project)


def test_audit_cli_reports_scope_and_exit_status(project: Path) -> None:
    command = [sys.executable, str(ROOT / "tools/audit.py"), str(project), "--json"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    assert completed.returncode == 0
    report = json.loads(completed.stdout)
    assert report["structural_pass"] is True
    assert report["full_conformance"] == "not-assessed"
    (project / "README.md").unlink()
    completed = subprocess.run(  # noqa: S603
        command[:-1], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 1
    assert "STRUCTURAL FAIL" in completed.stdout


def test_control_register_and_audit_template_stay_in_sync() -> None:
    baseline = (ROOT / "docs/baseline.md").read_text()
    template = (ROOT / "templates/common/docs/audit.md").read_text()
    assert set(re.findall(r"\|\s*([A-Z]+-\d+)\s*\|", baseline)) == CONTROLS
    assert (
        set(re.findall(r"\|\s*([A-Z]+-\d+)\s*\|\s*pending\s*\|", template)) == CONTROLS
    )


def test_framework_release_versions_are_consistent() -> None:
    manifest = json.loads((ROOT / ".standards.json").read_text())
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert (ROOT / "VERSION").read_text().strip() == FRAMEWORK_VERSION
    assert manifest["framework_version"] == FRAMEWORK_VERSION
    assert metadata["project"]["version"] == FRAMEWORK_VERSION


def test_component_layout_checks_declared_manifests_and_locks(project: Path) -> None:
    component = project / "backend"
    component.mkdir()
    (component / "requirements.txt").write_text("example==1.0\n")
    (component / "requirements.lock").write_text("example==1.0\n")
    write_manifest(
        project,
        components=[
            {
                "path": "backend",
                "profile": "python",
                "dependency_manifest": "requirements.txt",
                "lockfile": "requirements.lock",
            }
        ],
    )
    (project / "pyproject.toml").unlink()
    (project / "uv.lock").unlink()
    assert not failures(project)
    (component / "requirements.lock").unlink()
    assert "component:0:lockfile" in failures(project)


@pytest.mark.parametrize(
    "components",
    [
        None,
        [None],
        [
            {
                "path": "../outside",
                "profile": "python",
                "dependency_manifest": "requirements.txt",
                "lockfile": "requirements.lock",
            }
        ],
        [
            {
                "path": ".",
                "profile": "not-selected",
                "dependency_manifest": "pyproject.toml",
                "lockfile": "uv.lock",
            }
        ],
    ],
)
def test_invalid_component_metadata_fails(project: Path, components: object) -> None:
    write_manifest(project, components=components)
    assert any(item.startswith("component") for item in failures(project))
