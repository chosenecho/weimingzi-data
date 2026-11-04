#!/usr/bin/env python3
"""Validate canonical data, derived navigation and repository-local Markdown links."""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weimingzi_corpus.exports import navigation


def check_links(root):
    checked = 0
    for folder in [root, root / "docs"]:
        paths = folder.glob("*.md") if folder == root else folder.rglob("*.md")
        for path in paths:
            for target in re.findall(
                r"(?<!!)\[[^\n]*?\]\(([^\n]*?)\)", path.read_text(encoding="utf-8")
            ):
                target = target.split("#", 1)[0]
                if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    continue
                resolved = (path.parent / unquote(target)).resolve()
                if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                    raise ValueError(
                        f"{path.relative_to(root)}: broken local link {target}"
                    )
                checked += 1
    return checked


def main():
    root = Path(__file__).resolve().parents[1]
    print(navigation(root, check=True))
    print({"local_links_checked": check_links(root)})


if __name__ == "__main__":
    main()
