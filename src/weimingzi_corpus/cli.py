"""Offline daily commands; no credentials, servers or production state."""
import argparse
import json
import sys
from pathlib import Path

from .bundle import read_json, verify
from .pipeline import checkout, freeze, import_local, ingest, merge, project


def main(argv=None):
    parser = argparse.ArgumentParser(prog="wm-corpus")
    commands = parser.add_subparsers(dest="command", required=True)
    item = commands.add_parser("ingest", help="Keep a checked production delivery verbatim and build Silver")
    item.add_argument("--delivery", type=Path, required=True)
    item.add_argument("--out", type=Path, required=True)
    item = commands.add_parser("import-local", help="Import independently maintained articles or user content")
    item.add_argument("--records", type=Path, required=True)
    item.add_argument("--out", type=Path, required=True)
    item = commands.add_parser("merge")
    item.add_argument("--source", type=Path, required=True, action="append")
    item.add_argument("--out", type=Path, required=True)
    for name in ("checkout", "freeze"):
        item = commands.add_parser(name)
        item.add_argument("--source", type=Path, required=True)
        item.add_argument("--out", type=Path, required=True)
    item = commands.add_parser("project")
    item.add_argument("--source", type=Path, required=True)
    item.add_argument("--profile", type=Path, required=True)
    item.add_argument("--out", type=Path, required=True)
    item = commands.add_parser("verify")
    item.add_argument("--directory", type=Path, required=True)
    try:
        args = parser.parse_args(argv)
        if args.command == "ingest":
            result = ingest(args.delivery, args.out)
        elif args.command == "import-local":
            result = import_local(args.records, args.out)
        elif args.command == "merge":
            result = merge(args.source, args.out)
        elif args.command == "checkout":
            result = checkout(args.source, args.out)
        elif args.command == "freeze":
            result = freeze(args.source, args.out)
        elif args.command == "project":
            result = project(args.source, read_json(args.profile), args.out)
        else:
            result = verify(args.directory)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print("wm-corpus: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
