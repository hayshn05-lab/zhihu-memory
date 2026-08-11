from __future__ import annotations

import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from zhihu_memory.search import SearchEngine
from zhihu_memory.storage import MemoryStore, SchemaVersionError


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name, "memory.sqlite3"))
        with self.store.sync_transaction() as tx:
            tx.upsert_list("books", "读书")
            tx.upsert_list("news", "新闻追踪")
            tx.upsert_favorite(
                "https://x/rural", "《乡土中国》干货梳理", "费孝通、差序格局与礼治秩序", "作者甲", 1_646_000_000, "books"
            )
            tx.upsert_favorite(
                "https://x/war", "俄乌战争开局追踪", "乌克兰、俄罗斯与基辅局势连续更新", None, 1_646_172_800, "news"
            )
            tx.upsert_favorite(
                "https://x/econ", "中级微观经济学目录导航", "经济学习讲义", "作者乙", 1_713_734_400, "books"
            )
            tx.mark_success({"warnings": []})
        self.engine = SearchEngine(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_chinese_long_term_and_short_term_are_searchable(self):
        self.assertEqual(self.engine.search(["乡土中国"])[0]["url"], "https://x/rural")
        self.assertEqual(self.engine.search(["俄乌"])[0]["url"], "https://x/war")

    def test_scores_title_summary_and_list_matches_deterministically(self):
        results = self.engine.search(["经济学", "读书"], limit=10)
        self.assertEqual(results[0]["url"], "https://x/econ")
        self.assertEqual(results[0]["matched_terms"], ["经济学", "读书"])
        self.assertEqual(results, self.engine.search(["经济学", "读书"], limit=10))

    def test_date_and_list_filters_apply(self):
        before = self.engine.search(["战争"], before="2023-01-01")
        self.assertEqual([item["url"] for item in before], ["https://x/war"])
        books = self.engine.search(["经济"], list_name="读书")
        self.assertEqual([item["url"] for item in books], ["https://x/econ"])

    def test_result_contains_bounded_evidence_and_author_can_be_missing(self):
        result = self.engine.search(["乌克兰"])[0]
        self.assertIsNone(result["author"])
        self.assertLessEqual(len(result["snippet"]), 240)
        self.assertIn("乌克兰", result["snippet"])

    def test_status_marks_index_stale_after_seven_days(self):
        old = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        self.store.set_metadata("last_successful_sync", old)
        self.assertTrue(self.store.status()["stale"])

    def test_favorite_date_uses_local_timezone(self):
        from zhihu_memory.search import _date_timestamp, _local_date

        self.assertEqual(_local_date(1_646_005_143, timezone(timedelta(hours=8))), "2022-02-28")
        expected = int(datetime(2022, 2, 27, 23, 59, 59, tzinfo=timezone(timedelta(hours=8))).timestamp())
        self.assertEqual(_date_timestamp("2022-02-27", True, timezone(timedelta(hours=8))), expected)

    def test_date_filter_uses_next_midnight_across_dst(self):
        from zhihu_memory.search import _date_timestamp

        eastern = ZoneInfo("America/New_York")
        start = _date_timestamp("2024-03-10", False, eastern)
        end = _date_timestamp("2024-03-10", True, eastern)
        self.assertEqual(end + 1 - start, 23 * 3600)

    def test_like_fallback_remains_functional(self):
        self.store.search_backend = "like"
        self.assertEqual(self.engine.search(["乡土中国"])[0]["url"], "https://x/rural")

    def test_reopening_backfills_a_new_fts_index(self):
        self.store.connection.execute("DROP TABLE favorites_fts")
        self.store.connection.commit()
        path = self.store.path
        self.store.close()
        self.store = MemoryStore(path)
        self.engine = SearchEngine(self.store)
        self.assertEqual(self.engine.search(["乡土中国"])[0]["url"], "https://x/rural")

    def test_future_schema_is_rejected_without_downgrade(self):
        self.store.set_metadata("schema_version", "2")
        self.store.connection.commit()
        path = self.store.path
        self.store.close()
        with self.assertRaises(SchemaVersionError):
            MemoryStore(path)
        connection = __import__("sqlite3").connect(path)
        version = connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0]
        connection.close()
        self.assertEqual(version, "2")

    def test_ten_thousand_rows_search_under_200ms(self):
        with self.store.sync_transaction() as tx:
            for index in range(10_000):
                tx.upsert_favorite(
                    f"https://bulk/{index}",
                    f"合成收藏 {index}",
                    "用于性能测试的普通摘要",
                    "测试作者",
                    1_700_000_000 + index,
                    "books",
                )
            tx.upsert_favorite(
                "https://bulk/target", "目标主题收藏", "唯一检索证据", "测试作者", 1_800_000_000, "books"
            )
            tx.mark_success({"warnings": []})
        started = time.perf_counter()
        results = self.engine.search(["目标主题"])
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.assertEqual(results[0]["url"], "https://bulk/target")
        self.assertLess(elapsed_ms, 200, f"search took {elapsed_ms:.1f}ms")
