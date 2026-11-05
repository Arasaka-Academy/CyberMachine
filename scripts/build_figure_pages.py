#!/usr/bin/env python3
"""Stage the CyberMachine figure and linked public files for GitHub Pages."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIRECTORIES = ("docs/", "hardware/", "references/", "validation/")
PUBLIC_FILES = {"README.md", "AGENTS.md", "SHA256SUMS.txt"}


class PageLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.links.extend(value for key, value in attrs
                          if key in ("href", "src") and value)


def build(output: Path) -> None:
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    ).decode("utf-8").split("\0")
    # Only publish repository deliverables; work/, outputs/ and Git metadata stay out.
    sources = sorted({name for name in names if name in PUBLIC_FILES
                      or name.startswith(PUBLIC_DIRECTORIES)})
    output.mkdir(parents=True)
    for name in sources:
        source = ROOT / name
        if source.is_symlink():
            raise ValueError(f"Symbolic link cannot be published: {name}")
        if not source.is_file():
            continue
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    (output / ".nojekyll").touch()
    (output / "index.html").write_text(
        '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="refresh" content="0; url=docs/anatomy/r2/">'
        '<title>CyberMachine R2 · 交互结构图</title></head><body>'
        '<p><a href="docs/anatomy/r2/">打开 CyberMachine R2 交互结构图</a></p>'
        '<p><a href="docs/anatomy/r2/index-light.html">打开浅色主题</a></p>'
        '</body></html>\n', encoding="utf-8",
    )

    # Preserve repository-relative paths, including under the /CyberMachine/ prefix.
    checked = 0
    for page in sorted(output.rglob("*")):
        if page.suffix not in (".html", ".md"):
            continue
        content = page.read_text(encoding="utf-8")
        parser = PageLinks()
        parser.feed(content)
        links = parser.links
        if page.suffix == ".md":
            links += re.findall(r"!?\[[^\]]*\]\(([^\s)]+)\)", content)
        for link in links:
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path:
                continue
            target = (page.parent / unquote(url.path)).resolve()
            if url.path.startswith("/") or not target.is_relative_to(output):
                raise ValueError(f"Link leaves the project site in {page}: {link}")
            if not target.exists():
                raise ValueError(f"Missing local link in {page}: {link}")
            checked += 1
    count = sum(path.is_file() for path in output.rglob("*"))
    print(f"GitHub Pages: {count} files, {checked} local links verified: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/github-pages",
                        help="New output directory (default: outputs/github-pages)")
    args = parser.parse_args()
    build(args.output.resolve())


if __name__ == "__main__":
    main()
