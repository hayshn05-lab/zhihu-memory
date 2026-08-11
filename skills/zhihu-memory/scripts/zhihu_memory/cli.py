from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from .client import CliError, ZhihuCliClient
from .config import database_path
from .locator import CliNotFound, locate_cli
from .search import SearchEngine
from .storage import MemoryStore, SchemaVersionError
from .syncer import SyncEngine, SyncFailed


class UsageError(ValueError):
    pass


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


def emit(payload: dict[str, Any]) -> None:
    if hasattr(sys.stdout, "reconfigure") and (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def parser() -> argparse.ArgumentParser:
    root = JsonArgumentParser(prog="zhihu_memory.py")
    subcommands = root.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    sync = subcommands.add_parser("sync")
    sync.add_argument("--cli")
    search = subcommands.add_parser("search")
    search.add_argument("--term", action="append", required=True)
    search.add_argument("--after")
    search.add_argument("--before")
    search.add_argument("--list", dest="list_name")
    search.add_argument("--limit", type=int, default=10)
    return root


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
    except UsageError as exc:
        emit({"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": str(exc)}})
        return 2
    path = database_path()
    if args.command == "status" and not path.exists():
        emit(
            {
                "ok": True,
                "data": {
                    "indexed": False,
                    "database_path": str(path.resolve()),
                    "favorite_count": 0,
                    "last_successful_sync": None,
                    "search_backend": None,
                    "stale": False,
                    "warnings": [],
                },
            }
        )
        return 0
    if args.command == "search" and not path.exists():
        emit({"ok": False, "error": {"code": "NO_INDEX", "message": "Run sync before searching."}})
        return 4
    store: MemoryStore | None = None
    try:
        store = MemoryStore(path)
        if args.command == "status":
            emit({"ok": True, "data": store.status()})
            return 0
        if args.command == "sync":
            binary = locate_cli(args.cli)
            report = SyncEngine(store, ZhihuCliClient(binary)).run()
            emit({"ok": True, "data": report})
            return 0
        current_status = store.status()
        if not current_status["indexed"]:
            emit({"ok": False, "error": {"code": "NO_INDEX", "message": "Run sync before searching."}})
            return 4
        if args.limit < 1 or args.limit > 100:
            emit({"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "--limit must be 1..100"}})
            return 2
        results = SearchEngine(store).search(
            args.term, after=args.after, before=args.before, list_name=args.list_name, limit=args.limit
        )
        emit(
            {
                "ok": True,
                "data": {
                    "query": {"terms": args.term, "after": args.after, "before": args.before, "list": args.list_name},
                    "results": results,
                    "result_count": len(results),
                    "index": current_status,
                },
            }
        )
        return 0
    except CliNotFound as exc:
        emit({"ok": False, "error": {"code": "CLI_NOT_FOUND", "message": str(exc)}})
        return 5
    except CliError as exc:
        emit({"ok": False, "error": {"code": exc.code, "message": str(exc)}})
        return 6
    except SyncFailed as exc:
        emit({"ok": False, "error": {"code": "SYNC_FAILED", "message": str(exc)}})
        return 7
    except sqlite3.Error as exc:
        emit({"ok": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}})
        return 8
    except SchemaVersionError as exc:
        emit({"ok": False, "error": {"code": "INCOMPATIBLE_SCHEMA", "message": str(exc)}})
        return 9
    except (ValueError, OSError) as exc:
        emit({"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": str(exc)}})
        return 2
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    sys.exit(main())
