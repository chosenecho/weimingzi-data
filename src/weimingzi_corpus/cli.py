"""Small local commands for the canonical data. No services or producer gates."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from .data import (
    DIRECTORIES,
    TABLES,
    canonical,
    read_json,
    read_jsonl,
    records,
    safe_target,
    validate,
    write_json,
    write_jsonl,
)
from .exports import (
    catalog,
    markdown,
    navigation,
    review_markdown,
    sqlite_export,
    subtitle,
    text_of,
)


def find(root: Path, rid: str):
    for table in DIRECTORIES:
        path = safe_target(root, f"data/{table}/{rid}.json")
        if path.is_file():
            return read_json(path)
    raise ValueError("Unknown content record: " + rid)


def output_path(root: Path, output: str) -> Path:
    path = Path(output).resolve()
    for protected in ("data", "selections", "src", "tools", "tests", "docs", ".git"):
        if path.is_relative_to((root / protected).resolve()):
            raise ValueError(
                "Export cannot overwrite maintained data or code: " + str(path)
            )
    if path == root:
        raise ValueError("Export requires a file path")
    if (
        path.is_file()
        and path.is_relative_to(root)
        and not path.is_relative_to(root / ".cache")
    ):
        raise ValueError(
            "Export cannot overwrite an existing repository file: " + str(path)
        )
    return path


def import_record(root: Path, table: str, source: Path) -> int:
    """Insert canonical records after validating an isolated hard-linked projection."""
    incoming = (
        list(read_jsonl(source)) if source.suffix == ".jsonl" else read_json(source)
    )
    if isinstance(incoming, dict):
        incoming = [incoming]
    if not isinstance(incoming, list) or not incoming:
        raise ValueError("Expected one record, an array, or JSONL")
    existing = {r["id"]: r for r, _ in records(root, table)}
    new = []
    seen = set()
    for row in incoming:
        rid = row.get("id")
        if rid in seen:
            raise ValueError("Duplicate import ID: " + str(rid))
        seen.add(rid)
        if rid in existing:
            if existing[rid] != row:
                raise ValueError(
                    "Import would overwrite a different record: " + str(rid)
                )
        else:
            new.append(row)
    if not new:
        return 0
    cache = root / ".cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="import-", dir=cache) as name:
        candidate = Path(name)
        for folder in ("data", "selections"):
            shutil.copytree(root / folder, candidate / folder, copy_function=os.link)
        if table in TABLES:
            destination = candidate / "data" / (table + ".jsonl")
            destination.unlink()  # Detach before writing; never mutate a source hard link.
            write_jsonl(destination, [*existing.values(), *new])
        else:
            for row in new:
                destination = safe_target(candidate, f"data/{table}/{row['id']}.json")
                write_json(destination, row)
        validate(candidate)
        # No changes to the maintained tree occur before the full reference/type check.
        if table in TABLES:
            os.replace(
                candidate / "data" / (table + ".jsonl"),
                root / "data" / (table + ".jsonl"),
            )
        else:
            for row in new:
                destination = safe_target(root, f"data/{table}/{row['id']}.json")
                os.replace(
                    candidate / "data" / table / (row["id"] + ".json"), destination
                )
    return len(new)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    generated = commands.add_parser("generate")
    generated.add_argument("--check", action="store_true")
    imported = commands.add_parser("import")
    imported.add_argument("--table", choices=[*TABLES, *DIRECTORIES], required=True)
    imported.add_argument("source", type=Path)
    exported = commands.add_parser("export")
    exported.add_argument(
        "--format",
        choices=[
            "json",
            "jsonl",
            "txt",
            "markdown",
            "review",
            "srt",
            "vtt",
            "catalog",
            "sqlite",
        ],
        required=True,
    )
    scope = exported.add_mutually_exclusive_group()
    scope.add_argument("--id")
    scope.add_argument("--selection", choices=["training"])
    exported.add_argument("--output", required=True)
    searched = commands.add_parser("search")
    searched.add_argument("query")
    searched.add_argument(
        "--database", type=Path, default=Path(".cache/exports/corpus.sqlite3")
    )
    searched.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "validate":
            result = validate(root)
        elif args.command == "generate":
            result = navigation(root, args.check)
        elif args.command == "import":
            result = {"inserted": import_record(root, args.table, args.source)}
        elif args.command == "search":
            if not args.database.is_file():
                raise ValueError("Export a SQLite search database first")
            if not 1 <= args.limit <= 100:
                raise ValueError("Limit must be between 1 and 100")
            db = sqlite3.connect(
                "file:" + args.database.resolve().as_posix() + "?mode=ro", uri=True
            )
            try:
                # Bound parameters and a literal phrase keep punctuation out of the FTS grammar.
                phrase = '"' + args.query.replace('"', '""') + '"'
                if len(args.query) >= 3:
                    rows = db.execute(
                        "SELECT id,item_id,kind,snippet(search,3,'[',']','…',30) FROM search WHERE search MATCH ? LIMIT ?",
                        (phrase, args.limit),
                    ).fetchall()
                else:
                    literal = (
                        args.query.replace("\\", "\\\\")
                        .replace("%", "\\%")
                        .replace("_", "\\_")
                    )
                    rows = db.execute(
                        "SELECT id,item_id,kind,substr(text,1,180) FROM search WHERE text LIKE ? ESCAPE '\\' LIMIT ?",
                        ("%" + literal + "%", args.limit),
                    ).fetchall()
                result = [dict(zip(["id", "item_id", "kind", "text"], r)) for r in rows]
            finally:
                db.close()
        else:
            output = output_path(root, args.output)
            if args.format in {"catalog", "sqlite"}:
                if args.id or args.selection:
                    raise ValueError("Catalog/SQLite export covers all records")
                validate(root)
                if args.format == "sqlite":
                    sqlite_export(root, output)
                    value = None
                else:
                    value = catalog(root)
            else:
                if args.id:
                    rows = [find(root, args.id)]
                elif args.selection:
                    rows = [
                        find(root, e["reading_id"])
                        for e in read_json(root / "selections/training.json")["entries"]
                    ]
                else:
                    raise ValueError("Choose --id or --selection")
                if args.format == "jsonl":
                    value = "".join(canonical(r) + "\n" for r in rows)
                elif args.format == "json":
                    value = (
                        json.dumps(
                            rows[0] if args.id else rows, ensure_ascii=False, indent=2
                        )
                        + "\n"
                    )
                else:
                    if len(rows) != 1:
                        raise ValueError("This format requires a single --id")
                    row = rows[0]
                    if args.format in {"srt", "vtt"}:
                        value = subtitle(row, args.format)
                    elif args.format == "txt":
                        value = text_of(row)
                    else:
                        item = next(
                            r
                            for r, _ in records(root, "items")
                            if r["id"] == row["item_id"]
                        )
                        value = (
                            review_markdown(row, item)
                            if args.format == "review"
                            else markdown(row, item)
                        )
            if value is not None:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(value, encoding="utf-8", newline="\n")
            result = {"output": str(output)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
