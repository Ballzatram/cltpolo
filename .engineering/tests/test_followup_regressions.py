import subprocess
from pathlib import Path

import pytest

from tools.audit import action_findings
from tools.scaffold import create_project
from tools.secret_scan import choose_revision, trusted_bytes
from tools.site_check import inspect, srcset_urls


@pytest.mark.parametrize(
    "owner",
    [
        "owner.",
        "owner_",
        "org/..",
        "org//team",
        "org/team_",
        "bad--name",
        "-owner",
        "owner-",
        "x" * 40,
    ],
)
def test_invalid_owner_has_no_partial_output(tmp_path: Path, owner: str) -> None:
    target = tmp_path / "new-project"
    with pytest.raises(ValueError, match="Owner"):
        create_project(target, "python", owner)
    assert not target.exists()


@pytest.mark.parametrize("name", ["con", "aux", "prn", "nul", "com1", "lpt9"])
def test_windows_reserved_names_are_rejected(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match="reserved Windows"):
        create_project(tmp_path / "safe-parent", "python", "Ballzatram", name=name)


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_all_generated_owner_tokens_and_audit_commands_match(
    tmp_path: Path, language: str
) -> None:
    root = create_project(tmp_path / "actual-project", language, "actual-owner")
    for name in ["README.md", "docs/audit.md", "SECURITY.md"]:
        text = (root / name).read_text(encoding="utf-8")
        assert "**OWNER**" not in text and "**PROJECT_NAME**" not in text
        assert "__OWNER__" not in text and "__PROJECT_NAME__" not in text
    assert "actual-owner" in (root / "docs/audit.md").read_text()
    assert (
        "uv run --project .engineering --locked python .engineering/tools/audit.py ."
        in (root / "README.md").read_text()
    )


def test_missing_trusted_commit_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kw: subprocess.CompletedProcess(args, 128, b"", b""),
    )
    with pytest.raises(ValueError, match="Trusted commit is unavailable"):
        trusted_bytes(tmp_path, "a" * 40, ".gitleaks.toml", None)
    assert trusted_bytes(tmp_path, "0" * 40, ".gitleaks.toml", None).startswith(
        b"[extend]"
    )


def test_candidate_policy_uses_raw_commit_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *a, **kw: "tree " + "b" * 40 + "\nparent " + "a" * 40 + "\n\nmessage",
    )
    assert choose_revision(tmp_path, None, "c" * 40) == "a" * 40
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *a, **kw: "tree " + "b" * 40 + "\n\nroot commit",
    )
    assert choose_revision(tmp_path, None, "c" * 40) == "0" * 40
    with pytest.raises(ValueError, match="Candidate revision"):
        choose_revision(tmp_path, None, "mutable")


def test_docker_digest_is_not_an_action_commit(tmp_path: Path) -> None:
    p = tmp_path / "workflow.yml"
    p.write_text(
        "jobs:\n  test:\n    steps:\n      - uses: docker://image@" + "a" * 40 + "\n"
    )
    assert any(f.status == "fail" for f in action_findings(tmp_path, [p]))


def test_symlink_loop_is_a_normal_action_finding(tmp_path: Path) -> None:
    (tmp_path / "loop").symlink_to(tmp_path / "loop", target_is_directory=True)
    p = tmp_path / "workflow.yml"
    p.write_text("jobs:\n  test:\n    steps:\n      - uses: ./loop\n")
    assert any(f.status == "fail" for f in action_findings(tmp_path, [p]))


@pytest.mark.parametrize(
    "mapping", ["[]", '{"imports":[]}', '{"imports":{"lib/":"./modules"}}']
)
def test_invalid_import_maps_return_actionable_failures(
    tmp_path: Path, mapping: str
) -> None:
    (tmp_path / "index.html").write_text(
        '<html lang="en"><title>T</title><script type="importmap">'
        + mapping
        + "</script></html>"
    )
    assert any("invalid import map" in e for e in inspect(tmp_path, ["index.html"]))


def test_late_import_map_cannot_retroactively_fix_module(tmp_path: Path) -> None:
    (tmp_path / "entry.js").write_text('import "local";')
    (tmp_path / "local.js").write_text("export const value=1;")
    (tmp_path / "index.html").write_text(
        '<html lang="en"><title>T</title><script type="module" src="entry.js"></script><script type="importmap">{"imports":{"local":"./local.js"}}</script></html>'
    )
    assert any("unresolved bare module" in e for e in inspect(tmp_path, ["index.html"]))


def test_descriptorless_comma_is_part_of_the_url_per_browser_parser() -> None:
    assert srcset_urls("one.png,two.png") == ["one.png,two.png"]
