"""Check declared static pages, local resources and JavaScript syntax without executing page code."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.language = ""
        self.references: list[str] = []
        self.scripts: list[tuple[str, str]] = []
        self._in_title = False
        self._script: list[str] | None = None
        self._script_type = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "html":
            self.language = attributes.get("lang") or ""
        if tag == "title":
            self._in_title = True
        for key in ("src", "href"):
            if attributes.get(key):
                self.references.append(str(attributes[key]))
        if tag == "script" and not attributes.get("src"):
            self._script = []
            self._script_type = attributes.get("type") or "text/javascript"

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._script is not None:
            self._script.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._script is not None:
            self.scripts.append((self._script_type, "".join(self._script)))
            self._script = None


def local_target(root: Path, page: Path, reference: str) -> Path | None:
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    decoded = unquote(parsed.path)
    target = (
        (root if decoded.startswith("/") else page.parent) / decoded.lstrip("/")
    ).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Reference escapes the served site root")
    return target / "index.html" if target.is_dir() else target


def inspect(root: Path, pages: list[str], *, syntax: bool = True) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    node = shutil.which("node") if syntax else None
    if syntax and not node:
        return ["Node is required for JavaScript syntax checks."]
    scripts: set[Path] = set()
    for relative in pages:
        page = (root / relative).resolve()
        if not page.is_relative_to(root) or not page.is_file():
            errors.append(f"Missing page: {relative}")
            continue
        parser = Page()
        parser.feed(page.read_text(encoding="utf-8-sig"))
        if not parser.title.strip():
            errors.append(f"{relative}: page title is required")
        if not parser.language:
            errors.append(f"{relative}: document language is required")
        for reference in parser.references:
            try:
                target = local_target(root, page, reference)
                if target and not target.is_file():
                    errors.append(f"{relative}: missing local resource {reference}")
                elif target and target.suffix in (".js", ".mjs", ".cjs"):
                    scripts.add(target)
            except ValueError as exc:
                errors.append(f"{relative}: {exc}")
        if node:
            for index, (kind, code) in enumerate(parser.scripts):
                if (
                    kind not in ("module", "text/javascript", "application/javascript")
                    or not code.strip()
                ):
                    continue
                command = [
                    node,
                    "--check",
                    "--input-type=" + ("module" if kind == "module" else "commonjs"),
                ]
                # --check parses stdin only; it never evaluates page JavaScript.
                completed = subprocess.run(  # noqa: S603
                    command, input=code, text=True, capture_output=True, timeout=30
                )
                if completed.returncode:
                    errors.append(
                        f"{relative}: inline script {index} does not parse: {completed.stderr.strip()}"
                    )
    if node:
        for script in sorted(scripts):
            completed = subprocess.run(  # noqa: S603
                [node, "--check", str(script)],
                text=True,
                capture_output=True,
                timeout=30,
            )
            if completed.returncode:
                errors.append(
                    f"{script.relative_to(root)}: JavaScript does not parse: {completed.stderr.strip()}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--contract", type=Path, default=Path(".engineering/site-contract.json")
    )
    args = parser.parse_args()
    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        pages = contract["pages"]
        if (
            not isinstance(pages, list)
            or not pages
            or not all(isinstance(page, str) for page in pages)
        ):
            raise ValueError("Contract must declare a nonempty list of pages")
        errors = inspect(args.root, pages)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        errors = [str(exc)]
    for error in errors:
        print("FAIL: " + error)
    if not errors:
        print(
            "PASS: declared pages, local resources and JavaScript syntax; browser behavior requires separate tests."
        )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
