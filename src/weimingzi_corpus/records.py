"""Native archive records, immutable text references and atomic candidate installation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Iterable, Iterator

ENTITIES = ("items", "documents", "assets", "annotations")
JSONL_ENTITIES = ("items", "assets", "annotations")
RECORD_ID_PATTERN = re.compile(r"^[a-z]-[0-9a-f]{24,64}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def json_sha256(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_record_id(prefix: str, value) -> str:
    if not isinstance(prefix, str) or not re.fullmatch("[a-z]", prefix):
        raise ValueError("Record ID prefix must be one lowercase letter")
    return prefix + "-" + json_sha256(value)[:24]


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Nonfinite JSON number: {value}")


def _parse_json(text):
    return json.loads(text, object_pairs_hook=_object, parse_constant=_invalid_constant)


def read_json(path: Path):
    return _parse_json(Path(path).read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    yield _parse_json(line)
                except ValueError as exc:
                    raise ValueError(f"{path}:{number}: {exc}") from exc


def write_json(path: Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical_json(row) + "\n" for row in sorted(rows, key=lambda row: row["id"])), encoding="utf-8", newline="\n")


def validate_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or ":" in value or "\\" in value:
        raise ValueError(f"Unsafe relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError(f"Unsafe relative path: {value!r}")
    return path


def resolve_repository_path(root: Path, value: str) -> Path:
    root = Path(root).resolve()
    path = (root / Path(*validate_relative_path(value).parts)).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Path escapes root: {value}")
    return path


def _require_schema(root: Path) -> None:
    schema = read_json(Path(root) / "data/schema.json")
    expected = {"schema_version": 3, "entities": list(ENTITIES), "range_unit": "unicode_codepoint", "range_end": "exclusive"}
    if canonical_json(schema) != canonical_json(expected):
        raise ValueError("data/schema.json must declare the native four-entity schema 3 contract")


def _record_id(value: str) -> str:
    if not isinstance(value, str) or not RECORD_ID_PATTERN.fullmatch(value):
        raise ValueError(f"Invalid record ID: {value!r}")
    return value


def record_path(root: Path, entity: str, record_id: str) -> Path:
    if entity not in ENTITIES:
        raise ValueError(f"Unknown entity: {entity}")
    _record_id(record_id)
    relative = f"data/documents/{record_id}.json" if entity == "documents" else f"data/{entity}.jsonl"
    return resolve_repository_path(root, relative)


def iter_records(root: Path, entity: str, *, kind: str | None = None) -> Iterator[tuple[dict, Path]]:
    if entity not in ENTITIES:
        raise ValueError(f"Unknown entity: {entity}")
    root = Path(root)
    _require_schema(root)
    if entity == "documents":
        sources = ((read_json(path), path) for path in sorted((root / "data/documents").glob("*.json")))
    else:
        path = root / "data" / f"{entity}.jsonl"
        sources = ((row, path) for row in read_jsonl(path))
    for row, path in sources:
        if not isinstance(row, dict):
            raise ValueError(f"{path}: record must be an object")
        if kind is None or row.get("kind") == kind:
            yield row, path


def load_document(root: Path, record_id: str) -> dict:
    _require_schema(root)
    path = record_path(root, "documents", record_id)
    row = read_json(path)
    if not isinstance(row, dict) or row.get("id") != record_id:
        raise ValueError(f"{path}: document ID differs from filename")
    return row


def input_ids(record: dict, role: str) -> list[str]:
    return [edge["target_id"] for edge in record.get("inputs", []) if edge["role"] == role]


def document_hash_input(document: dict) -> dict:
    """Hash native content facts; absent fields remain absent, null remains null."""
    fields = ("kind", "inputs", "method", "language", "model", "time_unit", "text", "content", "blocks")
    return {key: document[key] for key in fields if key in document}


def _slice(text, bounds, context):
    if not isinstance(text, str) or not isinstance(bounds, list) or len(bounds) != 2 or any(type(n) is not int for n in bounds):
        raise ValueError(f"{context}: invalid Unicode codepoint range")
    start, end = bounds
    if not 0 <= start <= end <= len(text):
        raise ValueError(f"{context}: range outside text")
    return text[start:end]


def block_text(document: dict, block: dict) -> str:
    if ("range" in block) == ("literal" in block):
        raise ValueError(f"{document.get('id')}: exactly one of range/literal is required")
    if "literal" in block:
        if not isinstance(block["literal"], str):
            raise ValueError("Block literal must be text")
        return block["literal"]
    return _slice(document.get("text"), block["range"], document.get("id", "block"))


def resolve_input_text(document: dict, block: dict, entities: dict) -> str | None:
    """Resolve an exact current document source, never a historical input snapshot."""
    if "input_text" in block and "input_text_ref" in block:
        raise ValueError(f"{document.get('id')}: duplicate input text representation")
    if "input_text_ref" not in block:
        value = block.get("input_text")
        if value is not None and not isinstance(value, str):
            raise ValueError("input_text must be text or null")
        return value
    ref = block["input_text_ref"]
    if not isinstance(ref, dict) or set(ref) != {"target_id", "content_sha256", "source", "range"}:
        raise ValueError("Invalid input_text_ref fields")
    target_id = ref["target_id"]
    if target_id not in input_ids(document, "transcript"):
        raise ValueError(f"{document.get('id')}: input_text_ref must refer to a transcript input")
    target = entities["documents"][target_id]
    if target.get("kind") != "transcript":
        raise ValueError("input_text_ref target must be a transcript")
    if json_sha256(document_hash_input(target)) != ref["content_sha256"]:
        raise ValueError(f"{target_id}: input text content hash mismatch")
    if ref["source"] == "text":
        text = target["text"]
    elif ref["source"] == "blocks":
        text = "".join(block_text(target, value) for value in target["blocks"])
    else:
        raise ValueError(f"Unknown input text source: {ref['source']}")
    return _slice(text, ref["range"], "input_text_ref")


def _read_entities(root: Path) -> dict:
    entities = {entity: {} for entity in ENTITIES}
    all_ids = set()
    for entity in ENTITIES:
        for row, path in iter_records(root, entity):
            rid = _record_id(row.get("id"))
            if rid in all_ids:
                raise ValueError(f"Duplicate record ID: {rid}")
            if entity == "documents" and path.stem != rid:
                raise ValueError(f"{path}: document filename must equal id")
            all_ids.add(rid)
            entities[entity][rid] = row
    return entities


def validate_corpus(root: Path) -> dict:
    from .schema_v3 import validate_entities
    root = Path(root)
    entities = _read_entities(root)
    errors = validate_entities(root, entities)
    if errors:
        raise ValueError("Invalid native corpus: " + "; ".join(errors))
    counts = {entity: len(rows) for entity, rows in entities.items()}
    for entity, rows in entities.items():
        for row in rows.values():
            key = entity + "_" + row["kind"]
            counts[key] = counts.get(key, 0) + 1
    counts["blocks"] = sum(len(row.get("blocks", [])) for row in entities["documents"].values())
    return dict(sorted(counts.items()))


def install_candidate_updates(root: Path, candidate: Path, paths) -> None:
    """Install exactly the supplied candidate paths with rollback on I/O failure.

    Candidate files stay available for inspection. A missing candidate file is a
    deletion. Every replacement detaches hard links and all paths are confined.
    """
    root, candidate = Path(root).resolve(), Path(candidate).resolve()
    if root == candidate or candidate.is_relative_to(root) or root.is_relative_to(candidate):
        raise ValueError("Candidate and target roots must be disjoint")
    updates = []
    for relative in sorted({Path(path).as_posix() for path in paths}):
        target = resolve_repository_path(root, relative)
        source = resolve_repository_path(candidate, relative)
        if target.exists() and not target.is_file() or source.exists() and not source.is_file():
            raise ValueError(f"Installation requires regular files: {relative}")
        updates.append((relative, target, source))
    with tempfile.TemporaryDirectory(prefix=".record-rollback-", dir=candidate) as name:
        backup = Path(name)
        for relative, target, source in updates:
            if target.exists():
                saved = backup / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
        attempted = []
        try:
            for relative, target, source in updates:
                attempted.append((relative, target))
                if source.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    fd, name = tempfile.mkstemp(prefix=".record-install-", dir=target.parent)
                    os.close(fd)
                    temporary = Path(name)
                    try:
                        shutil.copy2(source, temporary)
                        os.replace(temporary, target)
                    finally:
                        temporary.unlink(missing_ok=True)
                else:
                    target.unlink(missing_ok=True)
        except OSError:
            for relative, target in reversed(attempted):
                saved = backup / relative
                if saved.exists():
                    # Copying back avoids depending on the failed replace operation.
                    shutil.copy2(saved, target)
                else:
                    target.unlink(missing_ok=True)
            raise


def write_record_updates(root: Path, updates: dict[str, Iterable[dict]]) -> list[Path]:
    """Validate the complete native candidate graph before installing any upsert."""
    from .schema_v3 import validate_entities
    root = Path(root).resolve()
    unknown = set(updates) - set(ENTITIES)
    if unknown:
        raise ValueError(f"Unknown entities: {sorted(unknown)}")
    entities = _read_entities(root)
    changed_entities = set()
    changed_documents = set()
    for entity, incoming in updates.items():
        seen = set()
        for row in incoming:
            if not isinstance(row, dict):
                raise ValueError(f"{entity}: incoming record must be an object")
            rid = _record_id(row.get("id"))
            if rid in seen:
                raise ValueError(f"Duplicate update ID: {rid}")
            seen.add(rid)
            if canonical_json(entities[entity].get(rid)) == canonical_json(row):
                continue
            entities[entity][rid] = row
            changed_entities.add(entity)
            if entity == "documents":
                changed_documents.add(rid)
    errors = validate_entities(root, entities)
    if errors:
        raise ValueError("Invalid native candidate: " + "; ".join(errors))
    paths = []
    with tempfile.TemporaryDirectory(prefix="native-candidate-", dir=root.parent) as name:
        candidate = Path(name)
        for entity in sorted(changed_entities):
            if entity == "documents":
                for rid in sorted(changed_documents):
                    relative = Path("data/documents") / (rid + ".json")
                    write_json(candidate / relative, entities[entity][rid])
                    paths.append(relative)
            else:
                relative = Path("data") / (entity + ".jsonl")
                write_jsonl(candidate / relative, entities[entity].values())
                if not (root / relative).exists() or (candidate / relative).read_bytes() != (root / relative).read_bytes():
                    paths.append(relative)
        install_candidate_updates(root, candidate, paths)
    return sorted(paths)
