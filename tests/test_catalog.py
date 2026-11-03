'''Catalog tests use temporary materials and do not need the corpus checkout.'''
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_repository as repository

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original_root = repository.ROOT
        repository.ROOT = self.root
        self.folder = 'data/transcripts/哲学与经典/item/P001'
        self.material(self.folder)

    def tearDown(self):
        repository.ROOT = self.original_root
        self.temp.cleanup()

    def material(self, folder):
        path = self.root / folder
        path.mkdir(parents=True, exist_ok=True)
        (path / 'text.md').write_text('A transcript.', encoding='utf-8')

    def row(self, **changes):
        return dict(kind='transcript', record_id='item:one', category='哲学与经典',
                    collection='data/transcripts/哲学与经典/item', title='同一内容',
                    part_title='', folder=self.folder, recommended_text=self.folder+'/text.md',
                    recommended_quality_status='', requires_review='', human_reviewed='') | changes

    def test_materials_share_a_collection_without_platform_requirement(self):
        supplement = 'data/transcripts/哲学与经典/item/补充版本/another'
        self.material(supplement)
        rows = [self.row(), self.row(record_id='another-format:two', folder=supplement,
                                    recommended_text=supplement+'/text.md', platform='another-format')]
        self.assertEqual(repository.validate_catalog(rows, self.root), {'data/transcripts/哲学与经典/item'})
        files = repository.generated_files(rows, {'counts': {}})
        self.assertIn('| 2 |', files['docs/catalog/哲学与经典.md'])
        page = files['data/transcripts/哲学与经典/item/README.md']
        self.assertIn('P001/text.md', page)
        self.assertIn('another/text.md', page)

    def test_dataset_uses_the_same_catalog_and_navigation(self):
        folder = 'data/datasets/校对数据'
        self.material(folder)
        row = self.row(kind='dataset', record_id='dataset:one', category='校对数据',
                       collection=folder, folder=folder, recommended_text=folder+'/text.md')
        self.assertEqual(repository.validate_catalog([row], self.root), set())
        files = repository.generated_files([row], {'counts': {}})
        self.assertIn('校对数据', files['docs/INDEX.md'])
        self.assertIn('[text.md](text.md)', files[folder+'/README.md'])

    def test_duplicate_material_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate record_id'):
            repository.validate_catalog([self.row(), self.row()], self.root)

    def test_traversal_and_absolute_paths_are_rejected(self):
        for path in ('../outside', '/outside', 'C:/outside', 'data/../outside', 'data\\outside'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Invalid catalog path'):
                repository.validate_catalog([self.row(folder=path)], self.root)

    def test_category_must_match_the_transcript_location(self):
        with self.assertRaisesRegex(ValueError, 'category/location disagree'):
            repository.validate_catalog([self.row(category='另一主题')], self.root)

    def test_reading_text_cannot_point_to_another_material(self):
        self.material('data/other')
        with self.assertRaisesRegex(ValueError, 'misplaced reading text'):
            repository.validate_catalog([self.row(recommended_text='data/other/text.md')], self.root)

    def test_missing_and_false_quality_flags_are_not_promoted(self):
        row = self.row(requires_review='False', human_reviewed='False')
        repository.validate_catalog([row], self.root)
        self.assertEqual(repository.material_status(row), '未登记')
        self.assertEqual(row['recommended_quality_status'], '')
        with self.assertRaisesRegex(ValueError, 'Invalid boolean'):
            repository.validate_catalog([self.row(human_reviewed='approved')], self.root)

    def test_empty_transcript_remains_visible_without_a_reading_link(self):
        row = self.row(recommended_text='', recognized_text_empty='True', requires_review='True')
        repository.validate_catalog([row], self.root)
        page = repository.generated_files([row], {'counts': {}})[row['collection']+'/README.md']
        self.assertIn('暂无正文', page)
        self.assertIn('需复核', page)
        self.assertNotIn('[正文]', page)

if __name__ == '__main__':
    unittest.main()
