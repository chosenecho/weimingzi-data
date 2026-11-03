import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('build_source_index', Path(__file__).resolve().parents[1] / 'tools/build_source_index.py')
index = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(index)


def catalog(**changes):
    return {
        'bvid': 'BV1234567890', 'page': '1', 'youtube_id': '',
        'title': '同一标题', 'part_title': '第一讲',
        'folder': 'data/bilibili/BV1234567890/P001',
        'recommended_text': 'data/bilibili/BV1234567890/P001/原始转录/transcript.txt',
        'recommended_quality_status': 'needs-review', 'recognized_text_empty': 'False',
        'youtube_requires_review': '', 'timed_exports_available': 'True', **changes,
    }


def youtube(**changes):
    return catalog(page='', youtube_id='abcDEF12_-3',
                   folder='data/youtube/abcDEF12_-3',
                   recommended_text='data/youtube/abcDEF12_-3/transcript.txt',
                   youtube_requires_review='True', **changes)


def audio():
    return {
        'audio_sha256': 'a' * 64, 'related_bvid': 'BV1234567890',
        'title': '同一标题', 'chapter': '第一讲', 'folder': 'data/audio/第一讲',
        'recommended_text': 'data/audio/第一讲/transcript.txt',
        'requires_review': 'False', 'human_reviewed': 'False', 'timed_exports_available': 'True',
    }


class SourceIndexTests(unittest.TestCase):
    def test_same_title_keeps_three_source_identities(self):
        rows = index.records([catalog(), youtube()], [audio()])
        self.assertEqual({r['record_id'] for r in rows}, {
            'bilibili:BV1234567890:p1', 'youtube:abcDEF12_-3', 'audio:' + 'a' * 64,
        })
        self.assertEqual(len({r['title'] for r in rows}), 1)

    def test_youtube_does_not_require_a_bilibili_parent(self):
        row, = index.records([youtube(bvid='')], [])
        self.assertEqual(row['record_id'], 'youtube:abcDEF12_-3')
        self.assertEqual(row['bvid'], '')

    def test_review_flags_are_not_promoted_to_approval(self):
        rows = {r['platform']: r for r in index.records([catalog(), youtube()], [audio()])}
        self.assertEqual(rows['audio']['human_reviewed'], 'False')
        self.assertEqual(rows['audio']['requires_review'], 'False')
        self.assertEqual(rows['audio']['quality_status'], '')
        self.assertEqual(rows['bilibili']['human_reviewed'], '')
        self.assertEqual(rows['bilibili']['requires_review'], '')
        self.assertEqual(rows['youtube']['requires_review'], 'True')

    def test_duplicate_youtube_mapping_is_not_a_second_source(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate source identity'):
            index.records([youtube(), youtube(bvid='BV0987654321')], [])

    def test_source_cannot_belong_to_two_platforms(self):
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            index.records([catalog(youtube_id='abcDEF12_-3')], [])

    def test_review_flags_reject_unrecognized_values(self):
        with self.assertRaisesRegex(ValueError, 'Invalid review flag'):
            index.records([catalog(recognized_text_empty='unknown')], [])

    def test_rejects_mismatched_identity_and_escaping_text(self):
        for changes in [
            {'folder': 'data/bilibili/BV0987654321/P001'},
            {'recommended_text': 'data/audio/another/transcript.txt'},
            {'recommended_text': 'data/bilibili/BV1234567890/P001/../../outside.txt'},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                index.records([catalog(**changes)], [])

    def test_empty_recognition_is_not_presented_as_readable_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'metadata').mkdir()
            for filename, rows in [('catalog.csv', [youtube(recognized_text_empty='True', bvid='')]),
                                   ('audio.csv', [audio()])]:
                with (root / 'metadata' / filename).open('w', encoding='utf-8', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
            output = index.generated_files(root)
            self.assertIn('无识别正文', output['docs/SOURCE-INDEX.md'])
            self.assertNotIn('(../data/youtube/abcDEF12_-3/transcript.txt)', output['docs/SOURCE-INDEX.md'])
            self.assertIn('data/youtube/abcDEF12_-3/transcript.txt', output['metadata/source-index.csv'])


if __name__ == '__main__':
    unittest.main()
