from pathlib import Path

import pytest

from tools.audit import action_findings, audit
from tools.scaffold import create_project
from tools.site_check import inspect, srcset_urls


@pytest.mark.parametrize("key", ["uses ", '"uses"', "'uses'"])
def test_yaml_keys_cannot_hide_unpinned_actions(tmp_path: Path, key: str) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        f"jobs:\n  test:\n    steps:\n      - {key}: actions/checkout@v4\n"
    )
    assert any(f.status == "fail" for f in action_findings(tmp_path, [workflow]))


def test_comment_and_run_text_are_not_action_references(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        'jobs:\n  test:\n    steps:\n      # uses: actions/a@v1\n      - run: |\n          echo "uses: actions/b@v1"\n'
    )
    assert not action_findings(tmp_path, [workflow])


def test_local_composites_and_reusable_workflows_are_recursive(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text("jobs:\n  test:\n    uses: ./reuse.yaml\n")
    (tmp_path / "reuse.yaml").write_text(
        "jobs:\n  build:\n    steps:\n      - uses: ./action\n"
    )
    action = tmp_path / "action"
    action.mkdir()
    (action / "action.yaml").write_text(
        "runs:\n  using: composite\n  steps:\n    - uses: ./action\n    - uses: actions/checkout@v4\n"
    )
    findings = action_findings(tmp_path, [workflow])
    assert any("checkout@v4" in f.check and f.status == "fail" for f in findings)
    (action / "action.yaml").write_text(
        "runs:\n  using: composite\n  steps:\n    - uses: actions/checkout@"
        + "a" * 40
        + "\n"
    )
    assert all(f.status == "pass" for f in action_findings(tmp_path, [workflow]))


@pytest.mark.parametrize(
    "text",
    ["[invalid", "null", "jobs: {test: {uses: 3}}", "jobs: {test: {uses: ./missing}}"],
)
def test_invalid_action_metadata_fails(tmp_path: Path, text: str) -> None:
    path = tmp_path / "workflow.yml"
    path.write_text(text)
    assert any(f.status == "fail" for f in action_findings(tmp_path, [path]))


def test_escaped_metadata_symlink_and_missing_selected_profile(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", "python", "Ballzatram")
    external = tmp_path / "external.md"
    external.write_text("Not stored in the project")
    (project / "README.md").unlink()
    (project / "README.md").symlink_to(external)
    (project / ".engineering/profiles/python.md").unlink()
    failed = {f.check for f in audit(project) if f.status == "fail"}
    assert "file:README.md" in failed
    assert "snapshot" in failed


def test_test_detection_requires_files_and_accepts_extensionless_tests(
    tmp_path: Path,
) -> None:
    project = create_project(tmp_path / "project", "python", "Ballzatram")
    for path in (project / "tests").glob("*.py"):
        path.unlink()
    (project / "tests/not_a_test.py").mkdir()
    assert any(f.check == "tests" and f.status == "fail" for f in audit(project))
    (project / "tests/test_cli").write_text("executable test")
    assert not any(f.check == "tests" and f.status == "fail" for f in audit(project))


def test_complete_snapshot_can_scaffold_another_project(tmp_path: Path) -> None:
    first = create_project(tmp_path / "first", "python", "Ballzatram")
    second = create_project(
        tmp_path / "second",
        "typescript",
        "Ballzatram",
        framework_root=first / ".engineering",
    )
    assert (second / ".engineering/tools/scaffold.py").is_file()
    assert (second / ".engineering/tests/test_audit.py").is_file()
    assert not any(f.status == "fail" for f in audit(second))


def page(root: Path, body: str, language: str = "en") -> None:
    (root / "index.html").write_text(
        f'<html lang="{language}"><title>Contract</title>{body}</html>'
    )


def test_base_url_fragments_and_srcset(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "one.png").write_bytes(b"image")
    (assets / "index.html").write_text('<html id="destination"></html>')
    page(
        tmp_path,
        '<base href="/assets/"><img srcset="one.png 1x, missing.png 2x"><a href="#destination">Go</a>',
    )
    errors = inspect(tmp_path, ["index.html"], syntax=False)
    assert errors == ["index.html: missing local resource missing.png"]
    (assets / "missing.png").write_bytes(b"image")
    assert not inspect(tmp_path, ["index.html"], syntax=False)
    assert srcset_urls("data:image/png;base64,abc 1x, one.png 2x") == [
        "data:image/png;base64,abc",
        "one.png",
    ]


def test_missing_fragment_and_blank_language_fail(tmp_path: Path) -> None:
    page(
        tmp_path,
        '<a href="#missing">Go</a><a name="legacy"></a><a href="#legacy">Old</a><a href="#top">Top</a>',
        " ",
    )
    errors = inspect(tmp_path, ["index.html"], syntax=False)
    assert len(errors) == 2
    assert any("language" in e for e in errors)
    assert any("missing fragment target #missing" in e for e in errors)


def test_script_modes_mime_types_and_import_graphs(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"type":"commonjs"}')
    (tmp_path / "module.js").write_text(
        'import "./child.js"; export const value = 1; throw new Error("never execute");'
    )
    (tmp_path / "child.js").write_text('import "./module.js";')
    page(tmp_path, '<script type="module" src="module.js"></script>')
    assert not inspect(tmp_path, ["index.html"])
    (tmp_path / "child.js").write_text('import "./missing.js";')
    assert any("missing local module" in e for e in inspect(tmp_path, ["index.html"]))
    (tmp_path / "child.js").write_text("with ({}) {}")
    assert any(
        "JavaScript does not parse" in e for e in inspect(tmp_path, ["index.html"])
    )
    page(tmp_path, '<script type="Text/JavaScript">const = invalid;</script>')
    assert any("inline script" in e for e in inspect(tmp_path, ["index.html"]))


def test_import_maps_and_unresolved_bare_modules(tmp_path: Path) -> None:
    (tmp_path / "entry.js").write_text('import "local";')
    (tmp_path / "local.js").write_text("export const value = 1;")
    page(
        tmp_path,
        '<script type="importmap">{"imports":{"local":"./local.js"}}</script><script type="module" src="entry.js"></script>',
    )
    assert not inspect(tmp_path, ["index.html"])
    page(tmp_path, '<script type="module" src="entry.js"></script>')
    assert any("unresolved bare module" in e for e in inspect(tmp_path, ["index.html"]))
