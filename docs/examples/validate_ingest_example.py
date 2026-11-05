"""Check design fixtures only; this is not the proposed production ingest entry."""

import copy
import hashlib
import json
import sys
import tempfile
import tomllib
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from weimingzi_corpus.records import JSONL_TABLES, JSON_RECORD_TABLES, json_sha256, validate_corpus, write_json, write_jsonl

bundle = ROOT / 'docs/examples/ingest-batch'
batch_schema = json.loads((ROOT / 'docs/contracts/ingest-batch-v1.schema.json').read_text(encoding='utf-8'))
asset_schema = json.loads((ROOT / 'docs/contracts/ingest-media-asset-v1.schema.json').read_text(encoding='utf-8'))
enrichment_schema = json.loads((ROOT / 'docs/contracts/ingest-enrichment-v1.schema.json').read_text(encoding='utf-8'))
for schema in (batch_schema, asset_schema, enrichment_schema):
    jsonschema.Draft202012Validator.check_schema(schema)
batch_validator = jsonschema.Draft202012Validator(batch_schema, format_checker=jsonschema.FormatChecker())
asset_validator = jsonschema.Draft202012Validator(asset_schema, format_checker=jsonschema.FormatChecker())
enrichment_validator = jsonschema.Draft202012Validator(enrichment_schema, format_checker=jsonschema.FormatChecker())
enrichment = json.loads((ROOT / 'docs/examples/ingest-enrichment.json').read_text(encoding='utf-8'))
enrichment_validator.validate(enrichment)
manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
batch_validator.validate(manifest)
identity = dict(manifest)
batch_id = identity.pop('batch_id')
assert json_sha256(identity) == batch_id
files = {entry['path']: entry for entry in manifest['files']}
assert len(files) == len(manifest['files'])
actual = {p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}
assert actual == set(files) | {'manifest.json'}
sources = {entry['source_id'] for entry in manifest['sources']}
rows = {table: [] for table in (*JSONL_TABLES, *JSON_RECORD_TABLES)}
seen, used, asset_count = set(), set(), 0
for operation in manifest['operations']:
    key = operation['table'], operation['record_id']
    assert key not in seen
    seen.add(key)
    relative = operation['path']
    assert relative == f'records/{operation["table"]}/{operation["record_id"]}.json'
    assert relative not in used
    used.add(relative)
    raw = (bundle / relative).read_bytes()
    entry = files[relative]
    assert len(raw) == entry['size_bytes']
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    row = json.loads(raw)
    assert row['id'] == operation['record_id']
    assert json_sha256(row) == operation['payload_sha256']
    assert set(operation['source_refs']) <= sources
    assert operation['op'] == 'insert' and operation['expected_record_sha256'] is None
    for asset in row.get('metadata', {}).get('media_assets', []):
        asset_validator.validate(asset)
        assert asset['sha256'] in asset['locator']['object_key']
        asset_count += 1
    rows[operation['table']].append(row)
assert used == set(files)
with tempfile.TemporaryDirectory(prefix='ingest-design-') as name:
    candidate = Path(name)
    for table in JSONL_TABLES:
        write_jsonl(candidate / f'data/{table}.jsonl', rows[table])
    for table in JSON_RECORD_TABLES:
        (candidate / 'data' / table).mkdir(parents=True)
        for row in rows[table]:
            write_json(candidate / 'data' / table / (row['id'] + '.json'), row)
    write_json(candidate / 'selections/training.json', {'schema_version': 2, 'entries': []})
    counts = validate_corpus(candidate)
policy = tomllib.loads((ROOT / 'docs/examples/ingest-policy.toml').read_text(encoding='utf-8'))
assert policy['enabled'] is False
assert policy['repository'] == manifest['target']['repository']
assert policy['limits']['files'] >= len(files)
assert sum(x['size_bytes'] for x in manifest['files']) <= policy['limits']['payload_total_bytes']
assert set(enrichment) <= set(policy['enrich']['items']['fields'])
assert set(enrichment['metadata']) <= set(policy['enrich']['items']['metadata_keys'])

bad_batches = []
for mutate in [
    lambda x: x['target'].__setitem__('repository', 'example/other'),
    lambda x: x.__setitem__('record_schema_version', True),
    lambda x: x.__setitem__('extra_field', 'not allowed'),
    lambda x: x['files'][0].__setitem__('path', '../escape.json'),
    lambda x: x['sources'][0].__setitem__('relation', 'referenced_content'),
    lambda x: x['operations'][0].__setitem__('op', 'enrich'),
    lambda x: x['operations'][0].__setitem__('op', 'attach_audio_distribution'),
    lambda x: x.__setitem__('created_at', 'invalid timestamp'),
]:
    bad = copy.deepcopy(manifest)
    mutate(bad)
    assert not batch_validator.is_valid(bad), bad
    bad_batches.append(True)
asset = next(row['metadata']['media_assets'][0] for row in rows['items'] if row.get('metadata', {}).get('media_assets'))
bad_asset = copy.deepcopy(asset)
bad_asset['mime_type'] = 'text/plain'
assert not asset_validator.is_valid(bad_asset)
tampered = copy.deepcopy(manifest)
tampered['producer']['run_id'] = 'tampered'
claimed = tampered.pop('batch_id')
assert claimed != json_sha256(tampered)
for forbidden in ({'text': 'overwrite body'}, {'metadata': {'title': 'not an observation array'}}, {}):
    assert not enrichment_validator.is_valid(forbidden)
print(json.dumps({'schemas_valid': 3, 'operations_verified': len(manifest['operations']), 'media_shapes_validated': asset_count,
                  'negative_checks': len(bad_batches) + 5, 'candidate_corpus': counts, 'policy_disabled': True}, ensure_ascii=False))
