#!/usr/bin/env python3
"""Validate canonical data, generated navigation and local Markdown destinations."""

import re
import sys
import unicodedata
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weimingzi_corpus.exports import generate_catalog_docs
from weimingzi_corpus.topics import generate_topic_catalog

# These are preserved source material or dated evidence, not current navigation.
# Links *to* these files are still checked. Their original bytes remain untouched.
HISTORICAL_FILES = {
    "docs/SCHEMA-V2.md",
    "docs/PRESERVATION-ROADMAP.md",
    "docs/evidence/issue-5-filler-only.md",
    "docs/evidence/issue-6-spoken-correction.md",
}
HISTORICAL_DIRECTORIES = {
    ("data", "artifacts"),
}
IGNORED_DIRECTORIES = {
    ".git", ".cache", ".venv", ".venv-workers", ".wrangler",
    "__pycache__", "node_modules", "python_modules",
}
# Inline destinations allow angle-bracket paths, titles and balanced parentheses.
DESTINATION = r'(<[^>\n]*>|(?:\\.|[^\s()<>]|\([^()\n]*\))+)'
INLINE_LINK = re.compile(
    r'(?<!!)\[(?:[^\[\]\n]|\[[^\]\n]*\])*\]\(\s*' + DESTINATION
    + r'''(?:\s+(?:"[^"\n]*"|'[^'\n]*'|\([^\n]*\)))?\s*\)'''
)
REFERENCE_LINK = re.compile(r"^ {0,3}\[[^\]\n]+\]:[ \t]*" + DESTINATION, re.MULTILINE)


class _HtmlNavigation(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = set()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id") is not None:
            self.anchors.add(attrs["id"])
        if tag == "a":
            if attrs.get("name") is not None:
                self.anchors.add(attrs["name"])
            if attrs.get("href") is not None:
                self.links.append(attrs["href"])


def _without_code_blocks(text):
    """Keep rendered prose, excluding fenced code and HTML comments."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    result = []
    fence = None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is None:
            if match:
                fence = match[1]
                result.append("\n")
            else:
                result.append(line)
        else:
            if (match and match[1][0] == fence[0]
                    and len(match[1]) >= len(fence) and not match[2].strip()):
                fence = None
            result.append("\n")
    return "".join(result)


def _without_inline_code(text):
    return re.sub(r"(`+)([^`]|(?!\1)`)*?\1", "", text)


def _heading_text(title):
    # Code spans render their contents literally, including underscores and <...>.
    code = []

    def preserve(match):
        code.append(match[2])
        return f"\x00CODE{len(code) - 1}\x00"

    title = re.sub(r"(`+)(.*?)\1", preserve, title)
    title = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", title)
    title = re.sub(r"<[^>]*>", "", title)
    title = re.sub(r"(\*\*|~~|\*)(.+?)\1", r"\2", title)
    title = re.sub(r"(?<!\w)(_+)(?=\S)(.+?)(?<=\S)\1(?!\w)", r"\2", title)
    title = unescape(title)
    for index, value in enumerate(code):
        title = title.replace(f"\x00CODE{index}\x00", value)
    return title.strip().lower()


def markdown_anchors(text):
    """Collect ATX/Setext heading anchors and explicit HTML IDs.

    Heading rules follow GitHub's section-link documentation: lowercase text,
    no formatting/punctuation, spaces as hyphens and unique numeric suffixes.
    Explicit HTML anchors do not participate in automatic suffix numbering.
    """
    text = _without_code_blocks(text)
    html = _HtmlNavigation()
    html.feed(_without_inline_code(text))
    anchors = set(html.anchors)
    generated = set()
    previous = ""
    for line in text.splitlines():
        heading = re.match(r"^ {0,3}#{1,6}[ \t]+(.*?)(?:[ \t]+#+[ \t]*)?$", line)
        title = heading[1] if heading else None
        if title is None and previous.strip() and re.fullmatch(r" {0,3}(?:=+|-+)[ \t]*", line):
            title = previous.strip()
        if title is not None:
            title = _heading_text(title)
            base = "".join(
                "-" if char == " " else char
                for char in title
                if char in " -_" or unicodedata.category(char)[0] in "LNM"
            )
            slug = base
            suffix = 0
            while slug in generated:
                suffix += 1
                slug = f"{base}-{suffix}"
            generated.add(slug)
            anchors.add(slug)
        previous = line if title is None else ""
    return anchors


def _link_destinations(text):
    text = _without_inline_code(_without_code_blocks(text))
    for pattern in (INLINE_LINK, REFERENCE_LINK):
        for match in pattern.finditer(text):
            target = match[1]
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            yield unescape(re.sub(r"\\([\\()<> ])", r"\1", target))
    html = _HtmlNavigation()
    html.feed(text)
    yield from html.links


def check_links(root):
    root = Path(root).resolve()
    checked = 0
    anchor_cache = {}
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if (relative.as_posix() in HISTORICAL_FILES
                or any(relative.parts[:len(parts)] == parts for parts in HISTORICAL_DIRECTORIES)
                or any(part in IGNORED_DIRECTORIES for part in relative.parts)):
            continue
        text = path.read_text(encoding="utf-8")
        for target in _link_destinations(text):
            url = urlsplit(target)
            if not target or url.scheme or url.netloc:
                continue
            local_path = unquote(url.path)
            if not local_path:
                resolved = path.resolve()
            elif local_path.startswith("/"):
                resolved = (root / local_path.lstrip("/")).resolve()
            else:
                resolved = (path.parent / local_path).resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                raise ValueError(f"{relative}: broken local link {target}")
            fragment = unquote(url.fragment)
            heading_path = resolved
            if fragment and resolved.is_dir():
                heading_path = resolved / "README.md"
                if not heading_path.is_file():
                    raise ValueError(f"{relative}: broken local anchor {target}")
            if fragment and heading_path.suffix.lower() == ".md":
                if heading_path not in anchor_cache:
                    anchor_cache[heading_path] = markdown_anchors(
                        heading_path.read_text(encoding="utf-8")
                    )
                if fragment not in anchor_cache[heading_path]:
                    raise ValueError(f"{relative}: broken local anchor {target}")
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
