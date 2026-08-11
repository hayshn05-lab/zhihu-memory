from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from zhihu_memory.storage import MemoryStore
from zhihu_memory.syncer import SyncEngine, SyncFailed

from tests.helpers import FakeClient, favorite


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name, "memory.sqlite3"))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_ignores_false_is_end_and_stops_after_two_empty_windows(self):
        client = FakeClient(
            lists=[{"UrlToken": "a", "Title": "默认收藏夹"}],
            pages={
                ("a", 0): [favorite("https://x/1", "第一页")],
                ("a", 50): [favorite("https://x/2", "隐藏的下一页")],
                ("a", 100): [],
                ("a", 150): [],
            },
        )
        report = SyncEngine(self.store, client).run()
        self.assertEqual(report["unique_items"], 2)
        self.assertEqual(report["api_calls"], 6)
        self.assertEqual(report["lists"][0]["stop_reason"], "two_empty_pages")
        self.assertEqual(self.store.count_favorites(), 2)

    def test_deduplicates_urls_but_preserves_memberships(self):
        shared = favorite("https://x/shared", "跨收藏夹")
        client = FakeClient(
            lists=[{"UrlToken": "a", "Title": "A"}, {"UrlToken": "b", "Title": "B"}],
            pages={("a", 0): [shared], ("b", 0): [shared]},
        )
        report = SyncEngine(self.store, client).run()
        self.assertEqual(report["raw_rows"], 2)
        self.assertEqual(report["unique_items"], 1)
        self.assertEqual(self.store.count_favorites(), 1)
        self.assertEqual(self.store.memberships_for("https://x/shared"), ["A", "B"])

    def test_repeated_sync_is_idempotent_and_missing_rows_are_not_deleted(self):
        first = FakeClient(
            lists=[{"UrlToken": "a", "Title": "A"}],
            pages={("a", 0): [favorite("https://x/1", "一"), favorite("https://x/2", "二")]},
        )
        SyncEngine(self.store, first).run()
        second = FakeClient(
            lists=[{"UrlToken": "a", "Title": "A"}],
            pages={("a", 0): [favorite("https://x/1", "一（更新）")]},
        )
        SyncEngine(self.store, second).run()
        self.assertEqual(self.store.count_favorites(), 2)
        self.assertEqual(self.store.get_favorite("https://x/1")["title"], "一（更新）")

    def test_failed_sync_keeps_previous_snapshot(self):
        initial = FakeClient(
            lists=[{"UrlToken": "a", "Title": "A"}],
            pages={("a", 0): [favorite("https://x/old", "旧数据")]},
        )
        SyncEngine(self.store, initial).run()
        failing = FakeClient(
            lists=[{"UrlToken": "a", "Title": "A"}],
            pages={("a", 0): [favorite("https://x/new", "不应提交")]},
            fail_at=("a", 50),
        )
        with self.assertRaises(SyncFailed):
            SyncEngine(self.store, failing).run()
        self.assertIsNone(self.store.get_favorite("https://x/new"))
        self.assertIsNotNone(self.store.get_favorite("https://x/old"))
        self.assertEqual(self.store.last_sync_run()["status"], "failed")

    def test_page_cap_is_reported_as_coverage_warning(self):
        client = FakeClient(
            lists=[{"UrlToken": "a", "Title": "A"}],
            pages={("a", offset): [favorite(f"https://x/{offset}", str(offset))] for offset in range(0, 150, 50)},
        )
        report = SyncEngine(self.store, client, max_pages=3).run()
        self.assertEqual(report["lists"][0]["stop_reason"], "page_cap")
        self.assertIn("PAGE_CAP_REACHED", report["warnings"])

    def test_exactly_fifty_lists_reports_unpageable_list_warning(self):
        lists = [{"UrlToken": str(index), "Title": str(index)} for index in range(50)]
        report = SyncEngine(self.store, FakeClient(lists=lists, pages={})).run()
        self.assertIn("FOLDER_LIST_LIMIT_REACHED", report["warnings"])
