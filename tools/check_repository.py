#!/usr/bin/env python3
'''Validate the catalog and generate navigation by content category.'''
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
import json
import os
from pathlib import PurePosixPath
import re
import sys
from urllib.parse import quote, unquote, urlsplit
from fetch_media import ROOT, COLLECTIONS, load_manifest, target_path, digest

GENERATED = '<!-- generated: tools/check_repository.py -->'
STATS_START = '<!-- archive-stats:start -->'
STATS_END = '<!-- archive-stats:end -->'
BOOLEAN_FIELDS = ('recognized_text_empty', 'requires_review', 'human_reviewed', 'timed_exports_available')

def require(condition, message):
    if not condition:
        raise ValueError(message)

def read_json(name):
    return json.loads(target_path(name).read_text(encoding='utf-8-sig'))

def read_csv(name):
    with target_path(name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'

def local_path(name, root):
    path = PurePosixPath(name)
    require(bool(name) and '\\' not in name and ':' not in name and not path.is_absolute()
            and '..' not in path.parts and str(path) == name and name != '.', 'Invalid catalog path: ' + name)
    result = (root / name).resolve()
    require(result.is_relative_to(root.resolve()), 'Catalog path escapes repository: ' + name)
    return result

def validate_catalog(rows, root=ROOT):
    '''Validate identity and location without requiring a platform.'''
    ids, folders, collections = set(), set(), set()
    for row in rows:
        identity = row.get('record_id', '')
        require(bool(identity) and identity not in ids, 'Empty or duplicate record_id: ' + identity)
        ids.add(identity)
        require(row.get('kind') in ('transcript', 'dataset'), 'Invalid material kind: ' + identity)
        category = row.get('category', '')
        require(bool(category) and category not in ('.', '..') and not any(c in category for c in '/\\:'), 'Invalid category: ' + identity)
        require(bool(row.get('title')), 'Missing title: ' + identity)
        collection, folder = local_path(row['collection'], root), local_path(row['folder'], root)
        require(row['collection'].startswith('data/'), 'Collection must be under data/: ' + identity)
        require(folder.is_relative_to(collection), 'Folder outside collection: ' + identity)
        require(folder.is_dir() and collection.is_dir(), 'Missing catalog folder: ' + row['folder'])
        require(row['folder'] not in folders, 'Duplicate catalog folder: ' + row['folder'])
        folders.add(row['folder'])
        if row['kind'] == 'transcript':
            parts = PurePosixPath(row['collection']).parts
            require(len(parts) == 4 and parts[:2] == ('data', 'transcripts') and parts[2] == category, 'Transcript category/location disagree: ' + identity)
            collections.add(row['collection'])
        if row.get('recommended_text'):
            text = local_path(row['recommended_text'], root)
            require(text.is_file() and text.is_relative_to(folder), 'Missing or misplaced reading text: ' + identity)
        for field in BOOLEAN_FIELDS:
            require(row.get(field, '') in ('', 'True', 'False'), 'Invalid boolean ' + field + ': ' + identity)
        if row.get('source_details'):
            require(isinstance(json.loads(row['source_details']), dict), 'Invalid source_details: ' + identity)
    return collections

def collect():
    catalog = read_csv('metadata/catalog.csv')
    collections = validate_catalog(catalog)
    actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'data/transcripts').glob('*/*') if p.is_dir()}
    require(collections == actual, 'Transcript directory/catalog sets differ')
    datasets = [r for r in catalog if r['kind'] == 'dataset']
    actual_datasets = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'data/datasets').iterdir() if p.is_dir()}
    require(actual_datasets == {r['folder'] for r in datasets if r['folder'].startswith('data/datasets/')}, 'Dataset directory/catalog sets differ')
    training = read_json('metadata/training-source.json')
    require(training['total'] == len(training['entries']), 'Training count mismatch')
    parts = {(r['bvid'], str(r['page'])) for r in catalog if r.get('bvid') and r.get('page')}
    selected = {(r['bvid'], str(r['page'])) for r in training['entries']}
    require(len(selected) == len(training['entries']) and selected.issubset(parts), 'Invalid training selection')
    user = read_json('data/user-content/summary.json')
    dynamics = len(list((ROOT / 'data/user-content/dynamics').glob('*.json')))
    articles = len(list((ROOT / 'data/user-content/articles').glob('*.txt')))
    lists = len(list((ROOT / 'data/user-content/article-lists').glob('*.json')))
    seasons = len(list((ROOT / 'data/user-content/channels').glob('season-*.md')))
    series = len(list((ROOT / 'data/user-content/channels').glob('series-*.md')))
    with (ROOT / 'data/user-content/videos.jsonl').open(encoding='utf-8') as stream:
        user_videos = sum(bool(line.strip()) for line in stream)
    require((dynamics, articles, lists, seasons, series, user_videos) == (user['dynamics_browser_saved'], user['article_bodies_saved'], user['article_lists_browser_saved'], user['seasons'], user['series'], user['videos_browser_saved']), 'User-content counts disagree with files')
    audio, assets = [], []
    for name in COLLECTIONS.values():
        manifest = load_manifest(name)
        audio.extend(manifest['files']); assets.extend(manifest['assets'])
        require(manifest['audio_count'] == len(manifest['files']), 'Media audio_count mismatch')
        require(manifest['total_audio_bytes'] == sum(r['bytes'] for r in manifest['files']), 'Media byte count mismatch')
    require(len(audio) == len({r['path'] for r in audio}), 'Duplicate audio restore destination')
    for row in audio:
        path = target_path(row['path'])
        require(path.is_file() or path.with_name(path.name + '.download.md').is_file(), 'Missing audio download entry: ' + row['path'])
    counts = {
        'catalog_records': len(catalog), 'transcript_records': len(catalog) - len(datasets),
        'content_collections': len(collections), 'content_categories': len({r['category'] for r in catalog if r['kind'] == 'transcript'}),
        'datasets': len(datasets), 'training_entries': len(training['entries']),
        'dynamics': dynamics, 'article_bodies': articles, 'article_lists': lists, 'seasons': seasons,
        'series': series, 'user_video_index': user_videos, 'audio_files': len(audio), 'audio_assets': len(assets),
        'audio_bytes': sum(r['bytes'] for r in audio), 'archive_bytes': sum(a['bytes'] for a in assets),
    }
    inputs = ['metadata/catalog.csv', 'metadata/training-source.json', 'data/user-content/summary.json', *COLLECTIONS.values()]
    summary = {'schema': 'weimingzi-repository-summary-v3', 'counts': counts,
               'input_sha256': {name: digest(target_path(name)) for name in inputs},
               'review_notice': 'Counts describe available materials, not human-approved content.'}
    return catalog, training, summary

def escaped(value):
    return str(value).replace('&', '&amp;').replace('|', '&#124;').replace('\n', ' ').replace('<', '&lt;').replace('>', '&gt;').replace('[', '&#91;').replace(']', '&#93;')

def link(name, document):
    return quote(os.path.relpath(ROOT / name, (ROOT / document).parent).replace(os.sep, '/'), safe='/.-_~')

def material_status(row):
    if row.get('recommended_quality_status'):
        return row['recommended_quality_status']
    if row.get('requires_review') == 'True':
        return '需复核'
    return '未登记'

def stats_table(c):
    return '\n'.join([
        '| 内容 | 数量 | 入口 |', '| --- | ---: | --- |',
        f'| 转录材料 | {c["transcript_records"]:,} 份 | [分类目录](docs/INDEX.md) |',
        f'| 内容条目 | {c["content_collections"]:,} 个，{c["content_categories"]} 类 | [主目录](metadata/catalog.csv) |',
        f'| 数据集 | {c["datasets"]} 组 | [分类目录](docs/INDEX.md) |',
        f'| 训练选稿 | {c["training_entries"]:,} 份 | [选稿索引](metadata/training-source.json) |',
        f'| 动态／文章正文 | {c["dynamics"]:,} 条／{c["article_bodies"]:,} 篇 | [用户内容](data/user-content/README.md) |',
        f'| 文集／合集／系列 | {c["article_lists"]:,}／{c["seasons"]:,}／{c["series"]:,} | [用户内容](data/user-content/README.md) |',
        f'| 可恢复音频 | {c["audio_files"]:,} 份，{c["audio_assets"]:,} 个分卷 | [下载指南](docs/DOWNLOAD.md) |',
    ]) + '\n'

def generated_files(catalog, summary):
    categories, collections = defaultdict(list), defaultdict(list)
    for row in catalog:
        categories[row['category']].append(row)
        collections[row['collection']].append(row)
    output = {'metadata/dataset-summary.json': json_text(summary)}
    main = [GENERATED, '# 分类目录', '',
            '按内容与材料类别浏览。完整字段见 [主目录](../metadata/catalog.csv)。', '',
            '| 类别 | 条目／数据集 | 材料记录 |', '| --- | ---: | ---: |']
    for category, rows in sorted(categories.items()):
        document = f'docs/catalog/{category}.md'
        grouped = defaultdict(list)
        for row in rows:
            grouped[row['collection']].append(row)
        main.append(f'| [{escaped(category)}]({link(document, "docs/INDEX.md")}) | {len(grouped)} | {len(rows)} |')
        lines = [GENERATED, '# ' + category, '', '[分类目录](../INDEX.md)', '',
                 '| 内容 | 材料数 | 文件入口 |', '| --- | ---: | --- |']
        for folder, items in sorted(grouped.items(), key=lambda pair: (pair[1][0]['title'], pair[0])):
            title = escaped(items[0]['title'])
            lines.append(f'| [{title}]({link(folder + "/README.md", document)}) | {len(items)} | [目录]({link(folder, document)}) |')
        output[document] = '\n'.join(lines + ['', '[分类目录](../INDEX.md)', ''])
    output['docs/INDEX.md'] = '\n'.join(main + ['', '材料数不代表审核通过数量。同一内容的分段和补充版本列在同一个条目下。', '', '[仓库首页](../README.md)', ''])
    for folder, rows in collections.items():
        document = folder + '/README.md'
        if rows[0]['kind'] == 'dataset':
            if not folder.startswith('data/datasets/'):
                continue
            lines = [GENERATED, '# ' + rows[0]['title'], '',
                     f'[分类目录]({link("docs/INDEX.md", document)}) · [主目录]({link("metadata/catalog.csv", document)})', '',
                     '按材料类别保存的 JSON、CSV、SQLite 或文本数据。文件内字段按各自格式读取。', '',
                     '| 文件／目录 |', '| --- |']
            for path in sorted((ROOT / folder).iterdir()):
                if path.name == 'README.md':
                    continue
                name = path.relative_to(ROOT).as_posix()
                lines.append(f'| [{escaped(path.name)}]({link(name, document)}) |')
        else:
            lines = [GENERATED, '# ' + escaped(rows[0]['title']), '',
                     f'[分类目录]({link("docs/INDEX.md", document)}) · [主目录]({link("metadata/catalog.csv", document)})', '',
                     '| 材料 | 正文 | 状态 | 文件 |', '| --- | --- | --- | --- |']
            for row in sorted(rows, key=lambda r: (int(r['page']) if r.get('page') else 10**9, r['record_id'])):
                reading = f'[正文]({link(row["recommended_text"], document)})' if row['recommended_text'] else '暂无正文'
                label = escaped(row.get('part_title') or row['title'])
                lines.append(f'| {label} | {reading} | {escaped(material_status(row))} | [目录]({link(row["folder"], document)}) |')
            lines += ['', '各份材料分别保留；关联目录不表示分段或音轨已经对齐。未登记状态不能视为审核通过。']
        output[document] = '\n'.join(lines + [''])
    return output

def check_generated(output, summary, update):
    for name, expected in output.items():
        path = target_path(name)
        if update:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected.encode('utf-8'))
        require(path.is_file() and path.read_text(encoding='utf-8') == expected, f'Generated file is stale: {name}; run --update-index')
    for path in (ROOT / 'docs/catalog').glob('*.md'):
        if path.relative_to(ROOT).as_posix() not in output:
            require(update and path.read_text(encoding='utf-8').startswith(GENERATED), 'Unexpected category page')
            path.unlink()
    path = ROOT / 'README.md'
    original = path.read_text(encoding='utf-8')
    require(original.count(STATS_START) == 1 and original.count(STATS_END) == 1, 'Missing README stats markers')
    before, rest = original.split(STATS_START, 1)
    _, after = rest.split(STATS_END, 1)
    expected = before + STATS_START + '\n' + stats_table(summary['counts']) + STATS_END + after
    if update:
        path.write_bytes(expected.encode('utf-8'))
    require(path.read_text(encoding='utf-8') == expected, 'README counts are stale; run --update-index')

def check_links():
    paths = [*ROOT.glob('*.md'), *(ROOT / 'docs').rglob('*.md'),
             *(ROOT / 'data').rglob('README.md'), *(ROOT / 'data').rglob('*.download.md'),
             ROOT / 'projects/uploader-23191782/README.md']
    count = 0
    for path in paths:
        if not path.is_file():
            continue
        body = path.read_text(encoding='utf-8-sig')
        fence = chr(96) * 3
        body = re.sub('^' + fence + '.*?^' + fence + '[^\n]*', '', body, flags=re.M | re.S)
        require(not re.search(r'^(<<<<<<<|=======|>>>>>>>)', body, re.M), f'Conflict marker: {path}')
        for match in re.finditer(r'(?<!\\)\[[^\]\n]*\]\(([^\n)]+)\)', body):
            href = match[1].strip('<>')
            parts = urlsplit(href)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            dest = (path.parent / unquote(parts.path)).resolve()
            require(dest.is_relative_to(ROOT.resolve()), f'Link escapes repository: {path}: {href}')
            require(dest.exists(), f'Broken link: {path.relative_to(ROOT)}: {href}')
            count += 1
    return count

def check_training(training, verify_hashes):
    checked = set()
    for row in training['entries']:
        require(bool(row.get('quality_status')), 'Training source has no review status')
        for path_key, hash_key in [('paths', 'sha256'), ('original_paths', 'original_sha256')]:
            for key, name in row[path_key].items():
                path = target_path(name)
                require(path.is_file(), 'Missing training source: ' + name)
                if verify_hashes and name not in checked:
                    require(digest(path) == row[hash_key][key], 'Training hash mismatch: ' + name)
                    checked.add(name)
    return len(checked)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update-index', action='store_true')
    parser.add_argument('--verify-hashes', action='store_true')
    args = parser.parse_args(argv)
    catalog, training, summary = collect()
    check_generated(generated_files(catalog, summary), summary, args.update_index)
    links = check_links()
    hashes = check_training(training, args.verify_hashes)
    print(json_text({'status': 'ok', 'counts': summary['counts'], 'navigation_links_checked': links, 'training_files_hashed': hashes}), end='')
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print(f'Repository check failed: {error}', file=sys.stderr)
        sys.exit(1)
