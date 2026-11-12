import hashlib
import subprocess
from pathlib import Path

import pytest

from tools.secret_scan import DEFAULT_CONFIG, scan, trusted_bytes


def test_base_configuration_wins_over_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".gitleaks.toml").write_text("candidate override")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 0, b"trusted base", b""),
    )
    assert trusted_bytes(tmp_path, "a" * 40, ".gitleaks.toml", None) == b"trusted base"


def test_bootstrap_is_checksum_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 128, b"", b""),
    )
    (tmp_path / ".gitleaks.toml").write_bytes(DEFAULT_CONFIG)
    digest = hashlib.sha256(DEFAULT_CONFIG).hexdigest()
    assert trusted_bytes(tmp_path, "a" * 40, ".gitleaks.toml", digest) == DEFAULT_CONFIG
    with pytest.raises(ValueError, match="checksum"):
        trusted_bytes(tmp_path, "a" * 40, ".gitleaks.toml", "b" * 64)
    assert trusted_bytes(tmp_path, "a" * 40, ".gitleaksignore", None) == b""
    with pytest.raises(ValueError, match="immutable"):
        trusted_bytes(tmp_path, "mutable-branch", ".gitleaks.toml", None)


def test_scan_uses_external_trusted_paths_and_disables_inline_bypass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if Path(args[0]).name.lower() in {"git", "git.exe"}:
            return subprocess.CompletedProcess(args, 128, b"", b"")
        assert Path(args[args.index("--config") + 1]).read_bytes() == DEFAULT_CONFIG
        assert not Path(args[args.index("--config") + 1]).is_relative_to(tmp_path)
        assert "--gitleaks-ignore-path" in args and "--ignore-gitleaks-allow" in args
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", run)
    assert scan(tmp_path, tmp_path / "gitleaks", "a" * 40) == 0
    assert len(calls) == 3


def test_config_cannot_extend_candidate_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def run(args, **kwargs):
        data = b'[extend]\npath="candidate.toml"' if args[-1].endswith(".toml") else b""
        return subprocess.CompletedProcess(args, 0, data, b"")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ValueError, match="cannot extend"):
        scan(tmp_path, tmp_path / "gitleaks", "a" * 40)


def test_cli_resolves_origin_head_and_reports_unavailable_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    import tools.secret_scan as module

    monkeypatch.setattr(sys, "argv", ["secret_scan"])
    monkeypatch.setattr(
        module.subprocess, "check_output", lambda *a, **kw: "a" * 40 + "\n"
    )
    called = []
    monkeypatch.setattr(module, "scan", lambda *args: called.append(args) or 0)
    assert module.main() == 0
    assert called[0][2] == "a" * 40
    monkeypatch.setattr(module.shutil, "which", lambda *a: None)
    assert module.main() == 1
