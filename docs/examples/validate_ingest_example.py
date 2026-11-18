"""Validate the current native synthetic bundle without touching maintained data."""

import copy
import json
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from weimingzi_corpus.ingest import IngestError, verify_batch
from weimingzi_corpus.ingest.manifest import validate_media
from weimingzi_corpus.ingest.merge import project, validate_scope
from weimingzi_corpus.ingest.planning import load_entities, validate_repository
from weimingzi_corpus.ingest.policy import POLICY
from weimingzi_corpus.records import ENTITIES, JSONL_ENTITIES, read_json, validate_corpus, write_json, write_jsonl, write_record_updates


def main():
    bundle = ROOT / "docs/examples/ingest-batch"
    batch = verify_batch(bundle)
    # jsonschema is an optional documentation check, never an ingest dependency.
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        schemas = [read_json(ROOT / "docs/contracts" / name) for name in (
            "ingest-batch-v2.schema.json", "ingest-media-asset-v2.schema.json")]
        for schema in schemas:
            jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schemas[0], format_checker=jsonschema.FormatChecker()).validate(batch.manifest)
    policy = tomllib.loads((ROOT / "docs/examples/ingest-policy.toml").read_text(encoding="utf-8"))
    assert policy["policy_version"] == POLICY["policy_version"]
    assert policy["enabled"] is False
    assert policy["limits"] == POLICY["limits"]
    assert policy["allowed_producers"] == POLICY["allowed_producers"]
    assert policy["allowed_media_bucket_aliases"] == POLICY["allowed_media_bucket_aliases"]
    with tempfile.TemporaryDirectory(prefix="native-ingest-example-") as folder:
        candidate = Path(folder)
        write_json(candidate / "data/schema.json", {"schema_version": 3, "entities": list(ENTITIES),
                                                   "range_unit": "unicode_codepoint", "range_end": "exclusive"})
        for entity in JSONL_ENTITIES:
            write_jsonl(candidate / "data" / (entity + ".jsonl"), [])
        (candidate / "data/documents").mkdir()
        entities = load_entities(candidate)
        baseline = {entity: {} for entity in ENTITIES}
        outcomes, conflicts = project(batch, entities)
        assert not conflicts, conflicts
        validate_scope(batch, entities, baseline)
        write_record_updates(candidate, {
            entity: [entities[entity][outcome["record_id"]] for outcome in outcomes if outcome["entity"] == entity]
            for entity in ENTITIES
        })
        counts = validate_corpus(candidate)
        supplemental = validate_repository(candidate)
        assert len(outcomes) == len(batch.manifest["operations"])
        assert all(outcome["outcome"] == "inserted" for outcome in outcomes)
        assert all(counts[entity] >= 0 for entity in ENTITIES)
        assert supplemental["media_assets"] == 2
    for payload in batch.payloads.values():
        for observation in payload.get("metadata", {}).get("media_assets", []):
            validate_media(observation)
            if jsonschema is not None:
                jsonschema.Draft202012Validator(schemas[1], format_checker=jsonschema.FormatChecker()).validate(observation)
            invalid = copy.deepcopy(observation)
            invalid["asset_version"] = 1
            try:
                validate_media(invalid)
            except IngestError:
                pass
            else:
                raise AssertionError("Historical media contract was accepted")
    print(json.dumps({"valid": True, "batch_id": batch.manifest["batch_id"],
                      "entities": {entity: counts[entity] for entity in ENTITIES},
                      "media_observations": supplemental["media_assets"],
                      "json_schema_checked": jsonschema is not None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
