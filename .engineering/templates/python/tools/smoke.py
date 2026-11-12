"""Verify the built wheel can be installed and used outside the source checkout."""

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    wheels = list((root / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one wheel in dist; remove stale artifacts.")
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        environment = work / "venv"
        # Commands use trusted interpreter paths and argument arrays, never a shell.
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)  # noqa: S603
        python = environment / (
            "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        )
        subprocess.run(  # noqa: S603
            [str(python), "-m", "pip", "install", "--no-deps", str(wheels[0])],
            cwd=work,
            check=True,
        )
        subprocess.run(  # noqa: S603
            [
                str(python),
                "-c",
                "from starter_package import normalize_label; "
                "assert normalize_label(' hello  world ') == 'hello world'",
            ],
            cwd=work,
            check=True,
        )


if __name__ == "__main__":
    main()
