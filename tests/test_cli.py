from __future__ import annotations

import json
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zhihu_memory.cli import emit
from zhihu_memory.storage import MemoryStore


ENTRY = Path(__file__).parents[1] / "skills" / "zhihu-memory" / "scripts" / "zhihu_memory.py"


class PublicCliTests(unittest.TestCase):
    def test_emit_reconfigures_non_utf8_stdout_for_user_content(self):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="gbk", errors="strict")
        with patch("sys.stdout", stream):
            emit({"summary": "⚠ coverage warning"})
            stream.flush()
        self.assertIn("⚠", buffer.getvalue().decode("utf-8"))

    def run_cli(self, *args, home: str):
        env = os.environ.copy()
        env["ZHIHU_MEMORY_HOME"] = home
        completed = subprocess.run(
            [sys.executable, str(ENTRY), *args], capture_output=True, text=True, encoding="utf-8", env=env
        )
        return completed, json.loads(completed.stdout)

    def test_status_is_json_when_index_does_not_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed, payload = self.run_cli("status", home=tmp)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["data"]["indexed"])

    def test_search_without_index_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed, payload = self.run_cli("search", "--term", "乡土中国", home=tmp)
        self.assertEqual(completed.returncode, 4)
        self.assertEqual(payload["error"]["code"], "NO_INDEX")

    def test_search_after_failed_initialization_still_returns_no_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp, "memory.sqlite3"))
            store.close()
            completed, payload = self.run_cli("search", "--term", "乡土中国", home=tmp)
        self.assertEqual(completed.returncode, 4)
        self.assertEqual(payload["error"]["code"], "NO_INDEX")

    def test_argument_errors_are_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed, payload = self.run_cli("search", home=tmp)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(payload["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(completed.stderr, "")

    def test_corrupt_database_returns_storage_error_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "memory.sqlite3").write_bytes(b"not a sqlite database")
            completed, payload = self.run_cli("status", home=tmp)
        self.assertEqual(completed.returncode, 8)
        self.assertEqual(payload["error"]["code"], "STORAGE_ERROR")
        self.assertNotIn("Traceback", completed.stderr)

    def test_future_schema_returns_compatibility_error_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp, "memory.sqlite3"))
            store.set_metadata("schema_version", "2")
            store.connection.commit()
            store.close()
            completed, payload = self.run_cli("status", home=tmp)
        self.assertEqual(completed.returncode, 9)
        self.assertEqual(payload["error"]["code"], "INCOMPATIBLE_SCHEMA")
