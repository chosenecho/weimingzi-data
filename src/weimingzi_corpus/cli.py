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

from .records import (
    JSON_RECORD_TABLES,
    JSONL_TABLES,
    canonical_json,
    read_json,
    read_jsonl,
    iter_records,
    resolve_repository_path,
    validate_corpus,
    write_json,
    write_jsonl,
)
from .exports import (
    render_catalog_csv,
    render_markdown,
    generate_catalog_docs,
    render_review_markdown,
    export_sqlite,
    render_subtitles,
    extract_text,
    iter_review_issues,
)


def load_content_record(root: Path, record_id: str):
    for table in JSON_RECORD_TABLES:
        path = resolve_repository_path(root, f"data/{table}/{record_id}.json")
        if path.is_file():
            return read_json(path)
    raise ValueError("Unknown content record: " + record_id)


def validate_export_path(root: Path, output: str) -> Path:
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


def import_records(root: Path, table: str, source: Path) -> int:
    """Insert canonical records after validating an isolated hard-linked projection."""
    incoming = (
        list(read_jsonl(source)) if source.suffix == ".jsonl" else read_json(source)
    )
    if isinstance(incoming, dict):
        incoming = [incoming]
    if not isinstance(incoming, list) or not incoming:
        raise ValueError("Expected one record, an array, or JSONL")
    existing = {r["id"]: r for r, _ in iter_records(root, table)}
    new = []
    seen = set()
    for row in incoming:
        record_id = row.get("id")
        if record_id in seen:
            raise ValueError("Duplicate import ID: " + str(record_id))
        seen.add(record_id)
        if record_id in existing:
            if existing[record_id] != row:
                raise ValueError(
                    "Import would overwrite a different record: " + str(record_id)
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
        if table in JSONL_TABLES:
            destination = candidate / "data" / (table + ".jsonl")
            destination.unlink()  # Detach before writing; never mutate a source hard link.
            write_jsonl(destination, [*existing.values(), *new])
        else:
            for row in new:
                destination = resolve_repository_path(
                    candidate, f"data/{table}/{row['id']}.json"
                )
                write_json(destination, row)
        validate_corpus(candidate)
        # No changes to the maintained tree occur before the full reference/type check.
        if table in JSONL_TABLES:
            os.replace(
                candidate / "data" / (table + ".jsonl"),
                root / "data" / (table + ".jsonl"),
            )
        else:
            for row in new:
                destination = resolve_repository_path(
                    root, f"data/{table}/{row['id']}.json"
                )
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
    ingest = commands.add_parser("ingest", help="Verify, plan and apply incremental batches")
    ingest_commands = ingest.add_subparsers(dest="ingest_command", required=True)
    ingest_commands.add_parser("validate-repository")
    verified = ingest_commands.add_parser("verify")
    verified.add_argument("batch", type=Path)
    planned = ingest_commands.add_parser("plan")
    planned.add_argument("batch", type=Path)
    planned.add_argument("--report", type=Path, required=True)
    applied = ingest_commands.add_parser("apply")
    applied.add_argument("batch", type=Path)
    applied.add_argument("--plan", type=Path, required=True)
    generated = commands.add_parser("generate")
    generated.add_argument("--check", action="store_true")
    imported = commands.add_parser("import")
    imported.add_argument(
        "--table", choices=[*JSONL_TABLES, *JSON_RECORD_TABLES], required=True
    )
    imported.add_argument("source", type=Path)
    package = commands.add_parser("import-package")
    package.add_argument("source", type=Path)
    coverage = commands.add_parser("coverage")
    coverage.add_argument("identifier")
    coverage.add_argument("--part", type=int)
    coverage.add_argument("--include-records", action="store_true")
    coverage.add_argument("--format", choices=["json", "jsonl"], default="json")
    coverage.add_argument("--output")
    topic = commands.add_parser("topic")
    topic.add_argument("identifier")
    topic.add_argument("--include-records", action="store_true")
    topic.add_argument("--output")
    exported = commands.add_parser("export")
    exported.add_argument(
        "--format",
        choices=[
            "json",
            "jsonl",
            "txt",
            "markdown",
            "review_markdown",
            "review_issues",
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
    if args.command == "ingest":
        from .ingest import (
            IngestError,
            apply_batch,
            plan_batch,
            validate_repository,
            verify_batch,
        )

        try:
            if args.ingest_command == "verify":
                result = verify_batch(args.batch).summary()
            elif args.ingest_command == "plan":
                report = plan_batch(root, args.batch, args.report)
                result = {
                    key: value
                    for key, value in report.items()
                    if key not in ("input_files", "operations", "changes")
                }
                result.update(
                    report=str(args.report.resolve()),
                    changed_files=len(report["changes"]),
                )
            elif args.ingest_command == "apply":
                result = apply_batch(root, args.batch, args.plan)
            else:
                result = {"status": "valid", **validate_repository(root)}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return result.get("exit_code", 0)
        except IngestError as error:
            print(json.dumps(error.as_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
            return error.exit_code
        except OSError as error:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": "LOCAL_IO_ERROR",
                        "message": str(error),
                        "exit_code": 5,
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 5
        except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as error:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": "PACKAGE_INTEGRITY_FAILED",
                        "message": str(error),
                        "exit_code": 2,
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 2
    try:
        if args.command == "validate":
            result = validate_corpus(root)
        elif args.command == "generate":
            result = generate_catalog_docs(root, args.check)
        elif args.command == "import":
            result = {"inserted": import_records(root, args.table, args.source)}
        elif args.command == "import-package":
            from .requested_results import import_requested_results

            result = import_requested_results(root, args.source)
        elif args.command == "coverage":
            from .coverage import CoverageIndex, coverage_jsonl

            result = CoverageIndex(root).report(
                args.identifier, args.part, args.include_records
            )
            if args.format == "jsonl" or args.output:
                value = (
                    coverage_jsonl(result)
                    if args.format == "jsonl"
                    else json.dumps(result, ensure_ascii=False, indent=2) + chr(10)
                )
                if args.output:
                    output = validate_export_path(root, args.output)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(value, encoding="utf-8", newline=chr(10))
                    result = {"output": str(output), "summary": result["summary"]}
                else:
                    print(value, end="")
                    return 0
        elif args.command == "topic":
            from .coverage import CoverageIndex
            from .topics import definitions, topic_report

            matched = [
                t for t in definitions(root) if args.identifier in (t["id"], t["title"])
            ]
            if len(matched) != 1:
                raise ValueError("Expected one topic: " + args.identifier)
            result = topic_report(CoverageIndex(root), matched[0], args.include_records)
            if args.output:
                output = validate_export_path(root, args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + chr(10),
                    encoding="utf-8",
                    newline=chr(10),
                )
                result = {"output": str(output), "counts": result["counts"]}
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
                        "SELECT id,item_id,kind,snippet(content_search,3,'[',']','…',30) FROM content_search WHERE content_search MATCH ? LIMIT ?",
                        (phrase, args.limit),
                    ).fetchall()
                else:
                    literal = (
                        args.query.replace("\\", "\\\\")
                        .replace("%", "\\%")
                        .replace("_", "\\_")
                    )
                    rows = db.execute(
                        "SELECT id,item_id,kind,substr(text,1,180) FROM content_search WHERE text LIKE ? ESCAPE '\\' LIMIT ?",
                        ("%" + literal + "%", args.limit),
                    ).fetchall()
                result = [dict(zip(["id", "item_id", "kind", "text"], r)) for r in rows]
            finally:
                db.close()
        else:
            output = validate_export_path(root, args.output)
            if args.format in {"catalog", "sqlite"}:
                if args.id or args.selection:
                    raise ValueError("Catalog/SQLite export covers all records")
                validate_corpus(root)
                if args.format == "sqlite":
                    export_sqlite(root, output)
                    value = None
                else:
                    value = render_catalog_csv(root)
            else:
                if args.id:
                    rows = [load_content_record(root, args.id)]
                elif args.selection:
                    rows = [
                        load_content_record(root, e["edited_transcript_id"])
                        for e in read_json(root / "selections/training.json")["entries"]
                    ]
                elif args.format == "review_issues":
                    rows = (r for r, _ in iter_records(root, "edited_transcripts"))
                else:
                    raise ValueError("Choose --id or --selection")
                if args.format == "review_issues":
                    value = "".join(
                        canonical_json(issue) + "\n"
                        for row in rows
                        for issue in iter_review_issues(row)
                    )
                elif args.format == "jsonl":
                    value = "".join(canonical_json(r) + "\n" for r in rows)
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
                        value = render_subtitles(row, args.format)
                    elif args.format == "txt":
                        value = extract_text(row)
                    else:
                        item = next(
                            r
                            for r, _ in iter_records(root, "items")
                            if r["id"] == row["item_id"]
                        )
                        value = (
                            render_review_markdown(row, item)
                            if args.format == "review_markdown"
                            else render_markdown(row, item)
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
