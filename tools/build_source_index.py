#!/usr/bin/env python3
"""Build discovery views from the maintained archive catalogs."""
from __future__ import annotations

import argparse
import csv
from io import StringIO
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
FIELDS = (
    'record_id', 'platform', 'source_id', 'bvid', 'page', 'title',
    'part_title', 'folder', 'recommended_text', 'quality_status', 'catalog',
    'recognized_text_empty', 'requires_review', 'human_reviewed', 'timed_exports_available',
)
GENERATED = '<!-- generated: tools/build_source_index.py -->'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def records(catalog, supplemental):
    result = []
    for row in catalog:
        page, youtube = row['page'], row['youtube_id']
        if bool(page) == bool(youtube):
            raise ValueError('Expected exactly one Bilibili part or YouTube ID')
        if (page or row['bvid']) and not re.fullmatch(r'BV[0-9A-Za-z]{10}', row['bvid']):
            raise ValueError('Invalid BV: ' + row['bvid'])
        if page:
            if not re.fullmatch(r'[1-9][0-9]*', page):
                raise ValueError('Invalid Bilibili page: ' + page)
            platform, source_id = 'bilibili', row['bvid']
            identity = f'bilibili:{source_id}:p{int(page)}'
        else:
            if not re.fullmatch(r'[0-9A-Za-z_-]{11}', youtube):
                raise ValueError('Invalid YouTube ID: ' + youtube)
            platform, source_id = 'youtube', youtube
            identity = 'youtube:' + source_id
        result.append(dict(zip(FIELDS, (
            identity, platform, source_id, row['bvid'], page, row['title'],
            row['part_title'], row['folder'], row['recommended_text'],
            row['recommended_quality_status'], 'metadata/catalog.csv',
            row['recognized_text_empty'], row['youtube_requires_review'] if youtube else '',
            '', row['timed_exports_available'],
        ))))
    for row in supplemental:
        sha = row['audio_sha256']
        if not re.fullmatch(r'[0-9a-f]{64}', sha):
            raise ValueError('Invalid supplemental audio SHA-256')
        # No single review-status field exists here. Do not infer approval.
        result.append(dict(zip(FIELDS, (
            'audio:' + sha, 'audio', sha, row['related_bvid'], '',
            row['title'], row['chapter'], row['folder'], row['recommended_text'],
            '', 'metadata/audio.csv',
            '', row['requires_review'], row['human_reviewed'], row['timed_exports_available'],
        ))))
    seen = set()
    for row in result:
        if row['record_id'] in seen:
            raise ValueError('Duplicate source identity: ' + row['record_id'])
        seen.add(row['record_id'])
        for field in ('recognized_text_empty', 'requires_review', 'human_reviewed', 'timed_exports_available'):
            if row[field] not in ('', 'True', 'False'):
                raise ValueError('Invalid review flag: ' + field)
        expected_folder = {'bilibili': f'data/bilibili/{row["bvid"]}/P{int(row["page"]):03d}' if row['page'] else '',
                           'youtube': 'data/youtube/' + row['source_id']}.get(row['platform'])
        if expected_folder and row['folder'] != expected_folder:
            raise ValueError('Source folder does not match its identity: ' + row['folder'])
        if row['platform'] == 'audio' and not row['folder'].startswith('data/audio/'):
            raise ValueError('Audio folder is outside data/audio')
        for field in ('folder', 'recommended_text'):
            name = row[field]
            if not name and field == 'recommended_text':
                continue
            path = PurePosixPath(name)
            if (not name or path.is_absolute() or '..' in path.parts
                    or ':' in name or chr(92) in name
                    or not path.parts or path.parts[0] != 'data'):
                raise ValueError('Unsafe archive path: ' + name)
        if row['recommended_text'] and not PurePosixPath(row['recommended_text']).is_relative_to(row['folder']):
            raise ValueError('Recommended text is outside its source folder')
    return sorted(result, key=lambda row: row['record_id'])


def cell(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('[', '&#91;').replace(']', '&#93;').replace('\n', ' ')


def link(label, path):
    return f'[{cell(label)}](../{quote(path, safe="/")})'


def generated_files(root=ROOT):
    rows = records(read_csv(root / 'metadata/catalog.csv'),
                   read_csv(root / 'metadata/audio.csv'))
    buffer = StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    counts = {platform: sum(row['platform'] == platform for row in rows)
              for platform in ('bilibili', 'youtube', 'audio')}
    lines = [
        GENERATED, '# 跨平台转录目录', '',
        '[统一 CSV](../metadata/source-index.csv) 汇集 B 站分 P、YouTube 音轨与补充音频。正文入口和状态来自现有目录；本页不重新选稿。',
        '', '| 来源 | 条目 | 阅读入口 |', '| --- | ---: | --- |',
        f'| B 站分 P | {counts["bilibili"]:,} | [分页视频目录](VIDEO-INDEX.md) |',
        f'| YouTube 音轨 | {counts["youtube"]:,} | [音轨列表](#youtube-音轨) |',
        f'| 补充音频 | {counts["audio"]:,} | [音频列表](#补充音频) |', '',
        '数量按来源单位分别计算，依据 [catalog.csv](../metadata/catalog.csv) 与 [audio.csv](../metadata/audio.csv)。跨平台对应不等于逐 P 对齐，也不自动去重为同一内容。',
        '动态与文章另见[用户内容](../data/user-content/README.md)。字段及稳定标识见[目录结构](STRUCTURE.md#统一来源标识)。',
        '', '## YouTube 音轨', '',
        '| YouTube ID | 标题 | 关联 BV | 阅读入口 | 记录状态 |',
        '| --- | --- | --- | --- | --- |',
    ]
    for row in rows:
        if row['platform'] == 'youtube':
            reading = ('无识别正文' if row['recognized_text_empty'] == 'True' else
                       link('正文', row['recommended_text']) if row['recommended_text'] else '无推荐正文')
            lines.append('| ' + ' | '.join((
                link(row['source_id'], row['folder']), cell(row['title']),
                link(row['bvid'], f'data/bilibili/{row["bvid"]}/README.md') if row['bvid'] else '无已确认关联',
                reading, cell(row['quality_status']),
            )) + ' |')
    lines.extend(['', '## 补充音频', '',
                  '| 音频 | 章节 | 阅读入口 | 来源与复核 |', '| --- | --- | --- | --- |'])
    for row in rows:
        if row['platform'] == 'audio':
            reading = link('正文', row['recommended_text']) if row['recommended_text'] else '无推荐正文'
            lines.append('| ' + ' | '.join((cell(row['title']), cell(row['part_title']), reading,
                                           link('音频记录', row['folder'] + '/README.md'))) + ' |')
    lines.extend(['', '补充音频的复核字段保留在原 CSV 与各音频记录中，统一索引的 quality_status 留空。',
                  '', '返回[仓库首页](../README.md)。', ''])
    return {'metadata/source-index.csv': buffer.getvalue(),
            'docs/SOURCE-INDEX.md': '\n'.join(lines)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check generated views without writing')
    args = parser.parse_args(argv)
    for name, expected in generated_files().items():
        path = ROOT / name
        if args.check:
            if not path.is_file() or path.read_text(encoding='utf-8') != expected:
                raise ValueError('Stale source index: ' + name)
        else:
            path.write_bytes(expected.encode('utf-8'))
    print('Source index is current.' if args.check else 'Source index updated.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print(f'Source index failed: {error}', file=sys.stderr)
        sys.exit(1)
