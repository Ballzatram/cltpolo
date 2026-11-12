"""Run the framework's blocking local checks with the active locked environment."""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    commands = [
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "mypy", "tools"],
        [sys.executable, "-m", "pytest"],
        [sys.executable, "-m", "compileall", "-q", "tools"],
        [sys.executable, "-m", "pip_audit"],
        [sys.executable, "tools/audit.py", "."],
    ]
    for command in commands:
        print("Running: " + " ".join(command), flush=True)
        # Trusted constant command list; never read commands from an audit target.
        subprocess.run(command, cwd=root, check=True)  # noqa: S603


if __name__ == "__main__":
    main()
