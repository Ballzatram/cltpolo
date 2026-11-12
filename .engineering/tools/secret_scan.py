"""Run Gitleaks with base-revision policy inputs outside the candidate checkout."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

DEFAULT_CONFIG = b"[extend]\nuseDefault = true\n"
SCANNER_VERSION = "8.30.1"


def trusted_bytes(root: Path, revision: str, name: str, bootstrap: str | None) -> bytes:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
        raise ValueError("Trusted revision must be an immutable Git commit SHA")
    git = shutil.which("git")
    if not git:
        raise OSError("Git is required to select trusted scanner inputs")
    if revision != "0" * 40:
        available = subprocess.run(  # noqa: S603
            [git, "cat-file", "-e", revision + "^{commit}"],
            cwd=root,
            capture_output=True,
            timeout=30,
        )
        if available.returncode:
            raise ValueError(
                "Trusted commit is unavailable; fetch complete history before scanning"
            )
        result = subprocess.run(  # noqa: S603
            [git, "show", f"{revision}:{name}"],
            cwd=root,
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
        tree = subprocess.run(  # noqa: S603
            [git, "ls-tree", "--name-only", revision, "--", name],
            cwd=root,
            capture_output=True,
            timeout=30,
        )
        if tree.returncode or tree.stdout.strip():
            raise ValueError("Trusted policy file cannot be read")
    path = root / name
    if bootstrap:
        candidate = path.read_bytes()
        if hashlib.sha256(candidate).hexdigest() != bootstrap:
            raise ValueError(f"Owner-reviewed bootstrap checksum differs: {name}")
        return candidate
    return DEFAULT_CONFIG if name.endswith(".toml") else b""


def choose_revision(root: Path, requested: str | None, candidate: str | None) -> str:
    if requested:
        return requested
    git = shutil.which("git")
    if not git:
        raise OSError("Git is required")
    if candidate:
        if not re.fullmatch(r"[0-9a-fA-F]{40}", candidate):
            raise ValueError("Candidate revision must be an immutable commit SHA")
        # Read the raw commit so a shallow boundary cannot masquerade as a root.
        commit = subprocess.check_output(  # noqa: S603
            [git, "cat-file", "-p", candidate], cwd=root, text=True, timeout=30
        )
        for line in commit.split("\n\n", 1)[0].splitlines():
            if line.startswith("parent "):
                return line.split()[1]
        return "0" * 40
    return subprocess.check_output(  # noqa: S603
        [git, "rev-parse", "--verify", "origin/HEAD"],
        cwd=root,
        text=True,
        timeout=30,
        stderr=subprocess.DEVNULL,
    ).strip()


def scan(
    root: Path,
    scanner: Path,
    revision: str,
    config_hash: str | None = None,
    ignore_hash: str | None = None,
) -> int:
    try:
        version = subprocess.run(  # noqa: S603
            [str(scanner.resolve()), "version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except OSError as exc:
        raise OSError(
            "Install Gitleaks 8.30.1 as documented in docs/local-tools.md"
        ) from exc
    if version.returncode or version.stdout.strip() != SCANNER_VERSION:
        raise ValueError("Gitleaks 8.30.1 is required; see docs/local-tools.md")
    config = trusted_bytes(root, revision, ".gitleaks.toml", config_hash)
    ignore = trusted_bytes(root, revision, ".gitleaksignore", ignore_hash)
    data = tomllib.loads(config.decode("utf-8"))
    if data.get("extend", {}).get("path"):
        raise ValueError(
            "Trusted scanner configuration cannot extend a candidate-controlled file"
        )
    git = shutil.which("git")
    if not git:
        raise OSError("Git is required")
    git_directory = Path(
        subprocess.check_output(  # noqa: S603
            [git, "rev-parse", "--absolute-git-dir"], cwd=root, text=True, timeout=30
        ).strip()
    ).resolve()
    with tempfile.TemporaryDirectory(prefix="trusted-gitleaks-") as td:
        folder = Path(td).resolve()
        if folder.is_relative_to(root.resolve()):
            raise ValueError(
                "Trusted scanner inputs must be outside the candidate checkout"
            )
        config_path, ignore_path = folder / "rules.toml", folder / "fingerprints"
        config_path.write_bytes(config)
        ignore_path.write_bytes(ignore)
        return subprocess.run(  # noqa: S603
            [
                str(scanner.resolve()),
                "git",
                str(git_directory),
                "--redact",
                "--no-banner",
                "--timeout",
                "120",
                "--config",
                str(config_path),
                "--gitleaks-ignore-path",
                str(ignore_path),
                "--ignore-gitleaks-allow",
            ],
            cwd=folder,
            timeout=150,
        ).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scanner", type=Path, default=Path("gitleaks"))
    parser.add_argument("--trusted-revision")
    parser.add_argument("--candidate-revision")
    parser.add_argument("--bootstrap-config-sha256")
    parser.add_argument("--bootstrap-ignore-sha256")
    args = parser.parse_args()
    try:
        revision = choose_revision(
            Path.cwd(), args.trusted_revision, args.candidate_revision
        )
        scanner = Path(shutil.which(str(args.scanner)) or args.scanner)
        return scan(
            Path.cwd(),
            scanner,
            revision,
            args.bootstrap_config_sha256,
            args.bootstrap_ignore_sha256,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Secret scan failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
