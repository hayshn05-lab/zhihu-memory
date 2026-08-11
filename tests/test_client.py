from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from zhihu_memory.client import CliError, ZhihuCliClient


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.client = ZhihuCliClient(Path("zhihu-cli"))

    @patch("zhihu_memory.client.subprocess.run")
    def test_invalid_json_is_structured_error(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="not-json", stderr="")
        with self.assertRaises(CliError) as raised:
            self.client.favorite_lists(50)
        self.assertEqual(raised.exception.code, "INVALID_CLI_JSON")

    @patch("zhihu_memory.client.subprocess.run")
    def test_auth_failure_preserves_cli_error_code(self, run):
        run.return_value = subprocess.CompletedProcess(
            [], 7, stdout='{"ok":false,"error":{"code":"AUTH_REQUIRED","message":"configure auth"}}', stderr=""
        )
        with self.assertRaises(CliError) as raised:
            self.client.verify()
        self.assertEqual(raised.exception.code, "AUTH_REQUIRED")

    @patch("zhihu_memory.client.subprocess.run")
    def test_items_extracts_data_items(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout='{"Data":{"Items":[{"Url":"https://x/1"}]}}', stderr="")
        self.assertEqual(self.client.favorite_items("a", 50, 50), [{"Url": "https://x/1"}])
        self.assertEqual(
            run.call_args.args[0],
            ["zhihu-cli", "me", "favorites", "items", "--url-token", "a", "--offset", "50", "--limit", "50"],
        )

    @patch("zhihu_memory.client.subprocess.run")
    def test_lists_rejects_missing_data_items(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout='{"Data":{}}', stderr="")
        with self.assertRaises(CliError) as raised:
            self.client.favorite_lists(50)
        self.assertEqual(raised.exception.code, "INVALID_CLI_RESPONSE")

    @patch("zhihu_memory.client.subprocess.run")
    def test_items_rejects_non_list_items(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout='{"Data":{"Items":{}}}', stderr="")
        with self.assertRaises(CliError) as raised:
            self.client.favorite_items("a", 0, 50)
        self.assertEqual(raised.exception.code, "INVALID_CLI_RESPONSE")
