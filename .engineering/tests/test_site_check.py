from pathlib import Path

import pytest

from tools.site_check import inspect, local_target


def test_static_contract_checks_actual_resources_and_metadata(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text('<html lang="en"><title>Test</title><img src="missing.png"></html>')
    assert any(
        "missing local resource" in item
        for item in inspect(tmp_path, ["index.html"], syntax=False)
    )
    (tmp_path / "missing.png").write_bytes(b"test")
    assert not inspect(tmp_path, ["index.html"], syntax=False)
    page.write_text("<html><title></title></html>")
    errors = inspect(tmp_path, ["index.html"], syntax=False)
    assert any("title" in item for item in errors)
    assert any("language" in item for item in errors)


def test_remote_and_fragment_references_are_not_fetched(tmp_path: Path) -> None:
    assert (
        local_target(tmp_path, tmp_path / "index.html", "https://example.invalid")
        is None
    )
    assert local_target(tmp_path, tmp_path / "index.html", "#part") is None


def test_encoded_traversal_and_missing_page_fail(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        local_target(tmp_path, tmp_path / "index.html", "%2e%2e/secret.txt")
    assert inspect(tmp_path, ["missing.html"], syntax=False) == [
        "Missing page: missing.html"
    ]


def test_directory_links_resolve_to_their_index(tmp_path: Path) -> None:
    (tmp_path / "route").mkdir()
    assert (
        local_target(tmp_path, tmp_path / "index.html", "/route/")
        == tmp_path / "route/index.html"
    )


def test_javascript_is_parsed_without_running_it(tmp_path: Path) -> None:
    (tmp_path / "app.js").write_text('throw new Error("must not execute");')
    (tmp_path / "index.html").write_text(
        '<html lang="en"><title>Test</title><script src="app.js"></script>'
        '<script>throw new Error("must not execute");</script>'
        '<script type="application/json">{"value":1}</script></html>'
    )
    assert not inspect(tmp_path, ["index.html"])
    (tmp_path / "app.js").write_text("const = invalid;")
    assert any(
        "JavaScript does not parse" in value
        for value in inspect(tmp_path, ["index.html"])
    )
    (tmp_path / "index.html").write_text(
        '<html lang="en"><title>T</title><script>const = invalid;</script></html>'
    )
    assert any("inline script" in value for value in inspect(tmp_path, ["index.html"]))


def test_site_checker_cli_contract_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    import sys

    from tools.site_check import main

    (tmp_path / "index.html").write_text('<html lang="en"><title>T</title></html>')
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"pages": ["index.html"]}))
    monkeypatch.setattr(
        sys,
        "argv",
        ["site_check", "--root", str(tmp_path), "--contract", str(contract)],
    )
    assert main() == 0
    contract.write_text('{"pages":[]}')
    assert main() == 1
    contract.write_text("bad-json")
    assert main() == 1


def test_missing_node_and_unsafe_resource_are_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tools.site_check.shutil.which", lambda _: None)
    assert inspect(tmp_path, ["index.html"]) == [
        "Node is required for JavaScript syntax checks."
    ]
    (tmp_path / "index.html").write_text(
        '<html lang="en"><title>T</title><img src="../secret"></html>'
    )
    assert any(
        "escapes" in error for error in inspect(tmp_path, ["index.html"], syntax=False)
    )
