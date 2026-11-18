"""Speaker/viewpoint evidence is anchored to exact native blocks and scope."""
import copy
from pathlib import Path
import tempfile
import unittest

from native_fixtures import fixture_records, rid, write_corpus
from weimingzi_corpus.records import validate_corpus
from weimingzi_corpus.schema_v3 import validate_native


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.rows = fixture_records()
        self.rows["annotations"] = [self.rows["annotations"][1]]
        self.attribution = self.rows["annotations"][0]
        write_corpus(self.root, self.rows)

    def tearDown(self):
        self.temp.cleanup()

    def assert_invalid(self, message):
        write_corpus(self.root, self.rows)
        with self.assertRaisesRegex(ValueError, message):
            validate_corpus(self.root)

    def test_valid_block_and_excerpt_records_are_counted(self):
        excerpt = copy.deepcopy(self.attribution)
        excerpt["id"] = rid("excerpt-attribution", "s")
        excerpt["anchor"]["excerpt"] = "二段"
        excerpt["viewpoint"] = "unknown"
        self.rows["annotations"].append(excerpt)
        write_corpus(self.root, self.rows)
        counts = validate_corpus(self.root)
        self.assertEqual(counts["annotations_segment_attribution"], 2)
        self.assertEqual(counts["annotations"], 2)
        self.assertFalse(self.rows["documents"][1]["quality"]["is_fully_human_reviewed"])

    def test_changed_block_text_invalidates_attribution(self):
        self.rows["documents"][1]["text"] = "原句😀。\n\n改过了。"
        self.assert_invalid("paragraph text hash mismatch")

    def test_literal_block_uses_precise_utf8_text(self):
        block = self.rows["documents"][1]["blocks"][1]
        block.pop("range")
        block["literal"] = "第二段。"
        write_corpus(self.root, self.rows)
        self.assertEqual(validate_native(self.root), [])
        block["literal"] = "第二段。 "
        self.assert_invalid("paragraph text hash mismatch")

    def test_excerpt_must_be_nonempty_substring_or_null(self):
        for value in ("段落里没有这句", "", 1, False):
            with self.subTest(value=value):
                self.attribution["anchor"]["excerpt"] = value
                self.assert_invalid("excerpt not found")

    def test_position_must_equal_native_block(self):
        for field, value in (("end", 2001), ("start", None), ("time_unit", "s")):
            with self.subTest(field=field):
                original = self.attribution["anchor"][field]
                self.attribution["anchor"][field] = value
                self.assert_invalid("start/end/time_unit differ")
                self.attribution["anchor"][field] = original

    def test_block_index_must_be_real_integer_in_range(self):
        for value in (2, -1, False, None):
            with self.subTest(value=value):
                self.attribution["anchor"]["paragraph_index"] = value
                self.assert_invalid("paragraph_index out of range")

    def test_owner_and_target_kind_and_cardinality(self):
        self.attribution["targets"][0]["target_id"] = self.rows["items"][0]["id"]
        self.assert_invalid("different item")
        self.attribution["targets"][0]["target_id"] = self.rows["items"][1]["id"]
        self.attribution["targets"][1]["target_id"] = self.rows["documents"][0]["id"]
        self.assert_invalid("wrong-kind applies_to")
        self.attribution["targets"][1]["target_id"] = self.rows["documents"][1]["id"]
        self.attribution["targets"].append({"role": "applies_to", "target_id": self.rows["documents"][2]["id"]})
        self.assert_invalid("exactly one applies_to")

    def test_enums_status_and_unknown_fields_are_closed(self):
        for field, value, message in (("speaker_role", "未明子", "invalid speaker_role"), ("viewpoint", "self_speech", "invalid viewpoint"), ("status", "model_suggested", "human_confirmed"), ("confidence", 0.9, "unknown fields")):
            with self.subTest(field=field):
                original = copy.deepcopy(self.attribution)
                self.attribution[field] = value
                self.assert_invalid(message)
                self.attribution.clear()
                self.attribution.update(original)
        self.attribution["review"]["model"] = "fixture"
        self.assert_invalid("unknown fields")

    def test_required_review_fields_typed_and_date_valid(self):
        for field, value, message in (("reviewed_on", "2026-13-01", "month|reviewed_on"), ("reviewed_on", "2026/11/06", "reviewed_on"), ("review_timezone", " ", "review_timezone"), ("basis", " ", "basis"), ("reviewer_reported_watched_original_video", "yes", "boolean")):
            with self.subTest(field=field):
                original = self.attribution["review"][field]
                self.attribution["review"][field] = value
                self.assert_invalid(message)
                self.attribution["review"][field] = original
        self.attribution["review"].pop("reviewer_label")
        self.assert_invalid("missing review evidence")

    def test_observed_timezone_label_is_preserved_without_conversion(self):
        self.attribution["review"]["review_timezone"] = "UTC"
        write_corpus(self.root, self.rows)
        self.assertEqual(validate_native(self.root), [])
        from weimingzi_corpus.records import iter_records
        actual = next(row for row, _ in iter_records(self.root, "annotations"))
        self.assertEqual(actual["review"]["review_timezone"], "UTC")
        for value in ("", None, False):
            with self.subTest(value=value):
                self.attribution["review"]["review_timezone"] = value
                self.assert_invalid("review_timezone")

    def test_id_prefix_and_duplicate_scope(self):
        old = self.attribution["id"]
        self.attribution["id"] = rid("wrong-prefix", "a")
        self.assert_invalid("s- prefix")
        self.attribution["id"] = old
        duplicate = copy.deepcopy(self.attribution)
        duplicate["id"] = rid("duplicate", "s")
        self.rows["annotations"].append(duplicate)
        self.assert_invalid("duplicate attribution")

    def test_order_has_no_meaning_for_applicability(self):
        self.attribution["targets"][1]["order"] = 0
        self.assert_invalid("only revision")


if __name__ == "__main__":
    unittest.main()
