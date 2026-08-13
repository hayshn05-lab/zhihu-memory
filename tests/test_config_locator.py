from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zhihu_memory.config import data_dir
from zhihu_memory.locator import CliNotFound, default_candidates, locate_cli


class ConfigLocatorTests(unittest.TestCase):
    def test_memory_home_override_wins(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"ZHIHU_MEMORY_HOME": tmp}):
            self.assertEqual(data_dir(), Path(tmp))

    def test_explicit_cli_wins_over_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            explicit = Path(tmp, "explicit.exe")
            fallback = Path(tmp, "fallback.exe")
            explicit.touch()
            fallback.touch()
            with patch.dict(os.environ, {"ZHIHU_CLI_BIN": str(fallback)}):
                self.assertEqual(locate_cli(str(explicit)), explicit.resolve())

    def test_cli_bin_environment_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp, "zhihu-cli")
            binary.touch()
            with patch.dict(os.environ, {"ZHIHU_CLI_BIN": str(binary)}, clear=True):
                self.assertEqual(locate_cli(), binary.resolve())

    def test_missing_cli_has_actionable_error(self):
        with patch.dict(os.environ, {}, clear=True), patch("zhihu_memory.locator.default_candidates", return_value=[]):
            with self.assertRaisesRegex(CliNotFound, "ZHIHU_CLI_BIN"):
                locate_cli()

    def test_linux_default_uses_xdg_data_home(self):
        with tempfile.TemporaryDirectory() as tmp, patch("zhihu_memory.locator.platform.system", return_value="Linux"), patch.dict(
            os.environ, {"XDG_DATA_HOME": tmp, "HOME": tmp, "USERPROFILE": tmp}, clear=True
        ):
            self.assertEqual(default_candidates()[0], Path(tmp, "zhihu-cli", "current", "zhihu-cli"))
