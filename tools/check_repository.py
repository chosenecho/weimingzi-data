#!/usr/bin/env python3
"""Validate canonical data, derived navigation and repository-local Markdown links."""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weimingzi_corpus.exports import generate_catalog_docs
from weimingzi_corpus.topics import generate_topic_catalog


def check_links(root):
    checked = 0
    ignored_directories = {
        ".git",
        ".cache",
        ".venv",
        ".venv-workers",
        ".wrangler",
        "__pycache__",
        "node_modules",
        "python_modules",
    }
    for path in root.rglob("*.md"):
        relative = path.relative_to(root)
        # Preserved Markdown is corpus content; its links describe original sources.
        if relative.parts[:2] == ("data", "artifacts"):
            continue
        if any(part in ignored_directories for part in relative.parts):
            continue
        for target in re.findall(
            r"(?<!!)\[[^\n]*?\]\(([^\n]*?)\)", path.read_text(encoding="utf-8")
        ):
            target = target.split("#", 1)[0]
            if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            resolved = (path.parent / unquote(target)).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                raise ValueError(f"{relative}: broken local link {target}")
            checked += 1
    return checked


def main():
    root = Path(__file__).resolve().parents[1]
    counts = generate_catalog_docs(root, check=True)
    counts.update(generate_topic_catalog(root, check=True))
    print(counts)
    print({"local_links_checked": check_links(root)})


if __name__ == "__main__":
    main()
