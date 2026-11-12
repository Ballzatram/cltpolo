"""Create a versioned starter in a new/empty directory without overwriting work."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]


def copy_framework(destination: Path, framework_root: Path = FRAMEWORK_ROOT) -> None:
    """Copy a complete runnable policy/tool package, never a partial tool snapshot."""
    destination.mkdir(parents=True, exist_ok=True)
    for directory in ("docs", "profiles", "tools", "templates", "tests", ".github"):
        source_root = framework_root / directory
        for source in template_files(source_root):
            target = destination / directory / source.relative_to(source_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    for filename in (
        "VERSION",
        "CHANGELOG.md",
        "README.md",
        "AGENTS.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        ".gitignore",
        ".editorconfig",
        ".gitattributes",
        ".standards.json",
        "pyproject.toml",
        "uv.lock",
    ):
        shutil.copyfile(framework_root / filename, destination / filename)


def template_files(template: Path) -> Iterator[Path]:
    """Prune local environments and generated artifacts before walking templates."""
    ignored = {
        ".venv",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        "coverage",
        ".ruff_cache",
        ".pytest_cache",
        ".mypy_cache",
        "htmlcov",
        ".git",
    }
    for directory, subdirectories, filenames in template.walk():
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if name not in ignored and not name.endswith(".egg-info")
        )
        for filename in sorted(filenames):
            if filename not in {".coverage", "coverage.xml", ".DS_Store", "Thumbs.db"}:
                yield directory / filename


def create_project(
    destination: Path,
    language: Literal["python", "typescript"],
    owner: str,
    *,
    name: str | None = None,
    framework_root: Path = FRAMEWORK_ROOT,
) -> Path:
    """Copy reviewed templates and policies; do not install or execute dependencies."""
    if language not in ("python", "typescript"):
        raise ValueError("Supported starters: python, typescript")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_.-]+)?", owner):
        raise ValueError(
            "Owner must be a GitHub username or organization/team, without @."
        )
    if destination.is_symlink():
        raise ValueError("Destination must not be a symlink.")
    destination = destination.resolve()
    if destination.exists() and (
        not destination.is_dir() or any(destination.iterdir())
    ):
        raise ValueError(
            "Destination must be a new or empty directory; nothing was overwritten."
        )
    if destination.is_relative_to(framework_root.resolve()):
        raise ValueError("Create consumer projects outside the framework repository.")
    project_name = name or destination.name.lower().replace("_", "-")
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", project_name):
        raise ValueError(
            "Project name must be lowercase words/numbers separated by hyphens."
        )
    package = project_name.replace("-", "_")
    if language == "python":
        import keyword

        if keyword.iskeyword(package):
            raise ValueError("Python package name must not be a reserved keyword.")
    replacements = {
        "__PROJECT_NAME__": project_name,
        "__OWNER__": owner,
        "starter-project": project_name,
        "starter_package": package,
    }
    destination.mkdir(parents=True, exist_ok=True)
    for template in (
        framework_root / "templates/common",
        framework_root / f"templates/{language}",
    ):
        for source in template_files(template):
            relative = str(source.relative_to(template))
            content = source.read_text(encoding="utf-8")
            for old, new in replacements.items():
                relative = relative.replace(old, new)
                content = content.replace(old, new)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
    snapshot = destination / ".engineering"
    copy_framework(snapshot, framework_root)
    commands = (
        {
            "format": "uv run --locked ruff format --check .",
            "lint": "uv run --locked ruff check .",
            "types": f"uv run --locked mypy src/{package}",
            "test": "uv run --locked pytest",
            "build": "uv run --locked python -m build --no-isolation",
            "security": "uv run --locked pip-audit --skip-editable --vulnerability-service osv",
        }
        if language == "python"
        else {
            key: f"npm run {value}"
            for key, value in {
                "format": "format:check",
                "lint": "lint",
                "types": "typecheck",
                "test": "test",
                "build": "build",
                "security": "security",
            }.items()
        }
    )
    manifest = {
        "schema_version": 1,
        "framework_version": (framework_root / "VERSION").read_text().strip(),
        "framework_source": ".engineering",
        "owner": owner,
        "risk_tier": "local",
        "lifecycle": "prototype",
        "profiles": [language],
        "commands": commands,
    }
    manifest_text = json.dumps(manifest, indent=2).replace(
        '"profiles": [\n    "' + language + '"\n  ]',
        '"profiles": ["' + language + '"]',
    )
    (destination / ".standards.json").write_text(
        manifest_text + "\n", encoding="utf-8", newline="\n"
    )
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--language", choices=("python", "typescript"), required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--name")
    args = parser.parse_args()
    try:
        created = create_project(
            args.destination, args.language, args.owner, name=args.name
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Cannot create starter: {exc}\n")
    print(
        f"Created {created}\nRead README.md to install dependencies and finish adoption. "
        "Manual standards review remains pending."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
