from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class CliError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ZhihuCliClient:
    def __init__(self, binary: Path):
        self.binary = binary

    def _run(self, *args: str) -> dict[str, Any]:
        completed = subprocess.run(
            [str(self.binary), *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        raw = completed.stdout.strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            message = completed.stderr.strip() or raw or "zhihu-cli returned no JSON"
            raise CliError("INVALID_CLI_JSON", message) from exc
        if not isinstance(payload, dict):
            raise CliError("INVALID_CLI_RESPONSE", "zhihu-cli JSON root must be an object")
        if completed.returncode != 0 or payload.get("ok") is False:
            error = payload.get("error") or {}
            raise CliError(str(error.get("code", "CLI_FAILED")), str(error.get("message", "zhihu-cli failed")))
        return payload

    @staticmethod
    def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("Data")
        if not isinstance(data, dict) or not isinstance(data.get("Items"), list):
            raise CliError("INVALID_CLI_RESPONSE", "zhihu-cli response must contain Data.Items as a list")
        items = data["Items"]
        if not all(isinstance(item, dict) for item in items):
            raise CliError("INVALID_CLI_RESPONSE", "each Data.Items entry must be an object")
        return items

    def verify(self) -> dict[str, Any]:
        return self._run("auth", "status", "--verify")

    def favorite_lists(self, limit: int) -> list[dict[str, Any]]:
        payload = self._run("me", "favorites", "lists", "--limit", str(limit))
        return self._items(payload)

    def favorite_items(self, token: str, offset: int, limit: int) -> list[dict[str, Any]]:
        payload = self._run(
            "me", "favorites", "items", "--url-token", token, "--offset", str(offset), "--limit", str(limit)
        )
        return self._items(payload)
