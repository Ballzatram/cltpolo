"""Check local HTML resources and parse script graphs without executing page code."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

ORIGIN = "https://standards.invalid/"
JS_TYPES = {
    "module",
    "text/javascript",
    "application/javascript",
    "text/ecmascript",
    "application/ecmascript",
    "application/x-javascript",
    "text/jscript",
    "text/livescript",
    "text/x-javascript",
    "text/x-ecmascript",
}
PARSER = """
const fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
try {
  const parsed = input.kind === 'module'
    ? new vm.SourceTextModule(input.code) : new vm.Script(input.code);
  const imports = input.kind === 'module'
    ? (parsed.moduleRequests?.map(request => request.specifier) ?? parsed.dependencySpecifiers) : [];
  process.stdout.write(JSON.stringify({imports}));
} catch (error) {
  process.stdout.write(JSON.stringify({error: error.name})); process.exitCode = 1;
}
"""


def srcset_urls(value: str) -> list[str]:
    """Tokenize URLs/descriptors; data-URI commas remain inside the URL token."""
    urls: list[str] = []
    position = 0
    while position < len(value):
        while position < len(value) and (
            value[position].isspace() or value[position] == ","
        ):
            position += 1
        start = position
        while position < len(value) and not value[position].isspace():
            position += 1
        token = value[start:position]
        if token:
            urls.append(token.rstrip(","))
        if token.endswith(","):
            continue
        while position < len(value) and value[position] != ",":
            position += 1
    return urls


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.language = ""
        self.base: str | None = None
        self.ids: set[str] = set()
        self.references: list[str] = []
        self.external_scripts: list[tuple[str, str]] = []
        self.scripts: list[tuple[str, str]] = []
        self._in_title = False
        self._script: list[str] | None = None
        self._script_type = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(str(attributes["id"]))
        if tag == "a" and attributes.get("name"):
            self.ids.add(str(attributes["name"]))
        if tag == "html":
            self.language = attributes.get("lang") or ""
        if tag == "title":
            self._in_title = True
        if tag == "base":
            if self.base is None and "href" in attributes:
                self.base = attributes["href"] or ""
            return
        for key in ("src", "href"):
            if attributes.get(key):
                self.references.append(str(attributes[key]))
        if attributes.get("srcset"):
            self.references.extend(srcset_urls(str(attributes["srcset"])))
        if tag == "script":
            kind = (
                (attributes.get("type") or "text/javascript")
                .split(";", 1)[0]
                .strip()
                .lower()
            )
            if attributes.get("src"):
                if kind in JS_TYPES:
                    self.external_scripts.append((kind, str(attributes["src"])))
            else:
                self._script = []
                self._script_type = kind

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


def _resolve(
    root: Path, page: Path, reference: str, base: str | None = None
) -> tuple[Path | None, str]:
    parsed = urlsplit(reference)
    if not base and not parsed.scheme and not parsed.netloc and parsed.path:
        decoded = unquote(parsed.path)
        raw = (
            (root if decoded.startswith("/") else page.parent) / decoded.lstrip("/")
        ).resolve()
        if not raw.is_relative_to(root):
            raise ValueError("Reference escapes the served site root")
    document = ORIGIN + page.relative_to(root).as_posix()
    url = urlsplit(urljoin(urljoin(document, base or ""), reference))
    if url.scheme != "https" or url.netloc != "standards.invalid":
        return None, ""
    target = (root / unquote(url.path).lstrip("/")).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Reference escapes the served site root")
    return (target / "index.html" if target.is_dir() else target), unquote(url.fragment)


def local_target(root: Path, page: Path, reference: str) -> Path | None:
    if not urlsplit(reference).path:
        return None
    decoded = unquote(urlsplit(reference).path)
    raw = (
        (root if decoded.startswith("/") else page.parent) / decoded.lstrip("/")
    ).resolve()
    if not raw.is_relative_to(root.resolve()):
        raise ValueError("Reference escapes the served site root")
    return _resolve(root.resolve(), page.resolve(), reference)[0]


def inspect(root: Path, pages: list[str], *, syntax: bool = True) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    node = shutil.which("node") if syntax else None
    if syntax and not node:
        return ["Node is required for JavaScript syntax checks."]
    documents: dict[Path, Page] = {}
    scripts: list[tuple[Path, str, dict[str, str]]] = []
    checked: set[tuple[Path, str, tuple[tuple[str, str], ...]]] = set()

    def read_page(path: Path) -> Page:
        if path not in documents:
            parser = Page()
            parser.feed(path.read_text(encoding="utf-8-sig"))
            documents[path] = parser
        return documents[path]

    def parse(code: str, kind: str, label: str) -> list[str]:
        if not node or not code.strip():
            return []
        completed = subprocess.run(  # noqa: S603
            [node, "--experimental-vm-modules", "-e", PARSER],
            input=json.dumps({"code": code, "kind": kind}),
            text=True,
            capture_output=True,
            timeout=30,
        )
        if completed.returncode:
            errors.append(f"{label}: JavaScript does not parse")
            return []
        value = json.loads(completed.stdout)
        return list(value["imports"])

    def enqueue(
        origin: Path, reference: str, imports: dict[str, str], base: str | None = None
    ) -> None:
        mapped = reference
        if not reference.startswith((".", "/")) and not urlsplit(reference).scheme:
            matches = [
                key
                for key in imports
                if reference == key or (key.endswith("/") and reference.startswith(key))
            ]
            if not matches:
                errors.append(
                    f"{origin.relative_to(root)}: unresolved bare module {reference}"
                )
                return
            key = max(matches, key=len)
            mapped = imports[key] + reference[len(key) :]
        target, _ = _resolve(root, origin, mapped, base)
        if target is not None:
            if not target.is_file():
                errors.append(
                    f"{origin.relative_to(root)}: missing local module {reference}"
                )
            else:
                scripts.append((target, "module", imports))

    for relative in pages:
        page = (root / relative).resolve()
        if not page.is_relative_to(root) or not page.is_file():
            errors.append(f"Missing page: {relative}")
            continue
        parser = read_page(page)
        if not parser.title.strip():
            errors.append(f"{relative}: page title is required")
        if not parser.language.strip():
            errors.append(f"{relative}: document language is required")
        import_map: dict[str, str] = {}
        for kind, code in parser.scripts:
            if kind == "importmap":
                data = json.loads(code)
                for key, value in data.get("imports", {}).items():
                    import_map[key] = urljoin(
                        urljoin(
                            ORIGIN + page.relative_to(root).as_posix(),
                            parser.base or "",
                        ),
                        value,
                    )
                if data.get("scopes"):
                    errors.append(
                        f"{relative}: scoped import maps require browser validation"
                    )
        for reference in parser.references:
            try:
                target, fragment = _resolve(root, page, reference, parser.base)
                if target is not None and not target.is_file():
                    errors.append(f"{relative}: missing local resource {reference}")
                elif target is not None and fragment:
                    anchor = fragment.split(":~:", 1)[0]
                    if (
                        anchor
                        and anchor.lower() != "top"
                        and target.suffix.lower() in {".html", ".htm"}
                        and anchor not in read_page(target).ids
                    ):
                        errors.append(
                            f"{relative}: missing fragment target {reference}"
                        )
            except ValueError as exc:
                errors.append(f"{relative}: {exc}")
        for kind, reference in parser.external_scripts:
            target, _ = _resolve(root, page, reference, parser.base)
            if target is not None and target.is_file():
                scripts.append(
                    (target, "module" if kind == "module" else "classic", import_map)
                )
        for index, (kind, code) in enumerate(parser.scripts):
            if kind in JS_TYPES:
                for reference in parse(
                    code, kind, f"{relative}: inline script {index}"
                ):
                    enqueue(page, reference, import_map, parser.base)
    while scripts:
        script, kind, imports = scripts.pop()
        key = script, kind, tuple(sorted(imports.items()))
        if key in checked:
            continue
        checked.add(key)
        for reference in parse(
            script.read_text(encoding="utf-8-sig"), kind, str(script.relative_to(root))
        ):
            enqueue(script, reference, imports)
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
            "PASS: declared pages, local resources, fragment targets and static script graphs; browser behavior requires separate tests."
        )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
