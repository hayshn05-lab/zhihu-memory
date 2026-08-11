from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import zhihu_memory.storage as storage
from zhihu_memory.storage import MemoryStore


class StorageSecurityTests(unittest.TestCase):
    def test_posix_creation_enforces_owner_only_modes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(storage, "_is_posix", return_value=True), patch.object(
            Path, "chmod"
        ) as chmod:
            store = MemoryStore(Path(tmp, "private", "memory.sqlite3"))
            store.close()
        chmod.assert_any_call(0o700)
        chmod.assert_any_call(0o600)

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not available on Windows")
    def test_actual_posix_modes_are_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "private", "memory.sqlite3")
            store = MemoryStore(path)
            store.close()
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
