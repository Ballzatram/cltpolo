"""Install and validate fresh reviewed starters in isolated temporary directories."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
    if not uv or not npm:
        raise SystemExit("Install the pinned uv and Node/npm toolchains first.")

    def run(command: list[str], directory: Path) -> None:
        print("Running: " + " ".join(command), flush=True)
        # Constant reviewed commands and resolved tool paths, with no shell interpolation.
        subprocess.run(command, cwd=directory, check=True)  # noqa: S603

    # TemporaryDirectory owns the exact directory it creates and cleans up.
    with tempfile.TemporaryDirectory(prefix="engineering-starters-") as temporary:
        parent = Path(temporary)
        for language in ("python", "typescript"):
            project = parent / f"verified-{language}"
            run(
                [
                    sys.executable,
                    str(root / "tools/scaffold.py"),
                    str(project),
                    "--language",
                    language,
                    "--owner",
                    "standards-reviewer",
                ],
                root,
            )
            if language == "python":
                commands = [
                    [uv, "sync", "--locked"],
                    [uv, "run", "--locked", "ruff", "format", "--check", "."],
                    [uv, "run", "--locked", "ruff", "check", "."],
                    [uv, "run", "--locked", "mypy", "src/verified_python"],
                    [uv, "run", "--locked", "pytest"],
                    [
                        uv,
                        "run",
                        "--locked",
                        "pip-audit",
                        "--skip-editable",
                        "--vulnerability-service",
                        "osv",
                    ],
                    [uv, "run", "--locked", "python", "-m", "build", "--no-isolation"],
                    [uv, "run", "--locked", "python", "tools/smoke.py"],
                ]
            else:
                commands = [[npm, "ci"]] + [
                    [npm, "run", command]
                    for command in (
                        "format:check",
                        "lint",
                        "typecheck",
                        "test",
                        "security",
                        "build",
                        "smoke",
                    )
                ]
            for command in commands:
                run(command, project)
            run([sys.executable, ".engineering/tools/audit.py", "."], project)


if __name__ == "__main__":
    main()
