from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Process tests invoke only this repository's scripts with argument arrays.
from tools.scaffold import FRAMEWORK_ROOT, create_project, template_files


def test_template_walk_excludes_generated_and_binary_caches(tmp_path: Path) -> None:
    for directory in (".ruff_cache", ".venv", "node_modules", "dist", "__pycache__"):
        cache = tmp_path / directory
        cache.mkdir()
        (cache / "binary").write_bytes(b"\xff\x00")
    (tmp_path / ".coverage").write_bytes(b"\xff\x00")
    expected = tmp_path / "source.py"
    expected.write_text("pass\n")
    assert list(template_files(tmp_path)) == [expected]


def test_nonempty_destination_preserves_existing_work(tmp_path: Path) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    precious = target / "work.txt"
    precious.write_text("keep me")
    with pytest.raises(ValueError, match="empty directory"):
        create_project(target, "python", "devin")
    assert precious.read_text() == "keep me"
    assert list(target.iterdir()) == [precious]


def test_existing_empty_directory_is_allowed(tmp_path: Path) -> None:
    target = tmp_path / "empty"
    target.mkdir()
    assert create_project(target, "python", "devin") == target


@pytest.mark.parametrize(
    ("language", "owner", "name"),
    [
        ("unknown", "devin", "sample"),
        ("python", "@devin", "sample"),
        ("python", "bad; command", "sample"),
        ("python", "devin", "Invalid_Name"),
        ("python", "devin", "class"),
        ("typescript", "devin", "../../escape"),
    ],
)
def test_bad_inputs_do_not_create_a_directory(
    tmp_path: Path, language: str, owner: str, name: str
) -> None:
    target = tmp_path / "new-project"
    with pytest.raises(ValueError):
        create_project(target, language, owner, name=name)
    assert not target.exists()


def test_file_destination_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "file"
    target.write_text("precious")
    with pytest.raises(ValueError):
        create_project(target, "python", "devin")
    assert target.read_text() == "precious"


def test_destination_inside_framework_is_refused() -> None:
    with pytest.raises(ValueError, match="outside"):
        create_project(FRAMEWORK_ROOT / "must-not-be-created", "python", "devin")


def test_name_substitution_covers_paths_code_metadata_and_lock(tmp_path: Path) -> None:
    project = create_project(tmp_path / "my-service", "python", "org/team")
    assert (project / "src/my_service/__init__.py").is_file()
    assert 'name = "my-service"' in (project / "pyproject.toml").read_text()
    assert 'name = "my-service"' in (project / "uv.lock").read_text()
    assert "from my_service import" in (project / "tests/test_labels.py").read_text()
    for path in project.rglob("*"):
        if path.is_file() and ".engineering" not in path.parts:
            content = path.read_text(encoding="utf-8")
            assert "__OWNER__" not in content
            assert "__PROJECT_NAME__" not in content
            assert "starter_package" not in content
    manifest = json.loads((project / ".standards.json").read_text())
    assert manifest["owner"] == "org/team"
    assert "src/my_service" in manifest["commands"]["types"]


def test_scaffold_cli_success_and_refusal(tmp_path: Path) -> None:
    target = tmp_path / "sample"
    command = [
        sys.executable,
        str(FRAMEWORK_ROOT / "tools/scaffold.py"),
        str(target),
        "--language",
        "typescript",
        "--owner",
        "devin",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    assert completed.returncode == 0
    assert "Manual standards review remains pending" in completed.stdout
    completed = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    assert completed.returncode == 1
    assert "nothing was overwritten" in completed.stderr
