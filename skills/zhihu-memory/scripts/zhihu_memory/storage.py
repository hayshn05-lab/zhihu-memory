from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = "1"


class SchemaVersionError(RuntimeError):
    pass


def _is_posix() -> bool:
    return os.name == "posix"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SyncTransaction:
    def __init__(self, store: "MemoryStore"):
        self.store = store
        self.connection = store.connection

    def upsert_list(self, token: str, title: str) -> None:
        now = utc_now()
        self.connection.execute(
            """INSERT INTO favorite_lists(url_token, title, first_seen_at, last_seen_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(url_token) DO UPDATE SET title=excluded.title, last_seen_at=excluded.last_seen_at""",
            (token, title, now, now),
        )

    def upsert_favorite(
        self,
        url: str,
        title: str,
        summary: str,
        author: str | None,
        fav_time: int,
        list_token: str,
    ) -> None:
        now = utc_now()
        self.connection.execute(
            """INSERT INTO favorites(url, title, summary, author_name, fav_time, first_seen_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(url) DO UPDATE SET
                 title=excluded.title, summary=excluded.summary, author_name=excluded.author_name,
                 fav_time=excluded.fav_time, last_seen_at=excluded.last_seen_at""",
            (url, title, summary, author, fav_time, now, now),
        )
        favorite_id = self.connection.execute("SELECT id FROM favorites WHERE url=?", (url,)).fetchone()[0]
        list_id = self.connection.execute("SELECT id FROM favorite_lists WHERE url_token=?", (list_token,)).fetchone()[0]
        self.connection.execute(
            """INSERT INTO favorite_memberships(favorite_id, list_id, first_seen_at, last_seen_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(favorite_id, list_id) DO UPDATE SET last_seen_at=excluded.last_seen_at""",
            (favorite_id, list_id, now, now),
        )
        if self.store.search_backend == "fts5-trigram":
            self.connection.execute("DELETE FROM favorites_fts WHERE favorite_id=?", (favorite_id,))
            self.connection.execute(
                "INSERT INTO favorites_fts(favorite_id, title, summary) VALUES (?, ?, ?)",
                (favorite_id, title, summary),
            )

    def mark_success(self, report: dict[str, Any]) -> None:
        finished = utc_now()
        self.store.set_metadata("last_successful_sync", finished)
        self.store.set_metadata("last_warnings", json.dumps(report.get("warnings", []), ensure_ascii=False))
        self.connection.execute(
            "INSERT INTO sync_runs(started_at, finished_at, status, report_json) VALUES (?, ?, 'success', ?)",
            (report.get("started_at", finished), finished, json.dumps(report, ensure_ascii=False)),
        )


class MemoryStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        if _is_posix():
            path.parent.chmod(0o700)
        self.connection = sqlite3.connect(path)
        if _is_posix():
            path.chmod(0o600)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute("PRAGMA foreign_keys=ON")
            existing_version = self._existing_schema_version()
            if existing_version is not None and existing_version != SCHEMA_VERSION:
                raise SchemaVersionError(
                    f"database schema {existing_version!r} is incompatible with supported version {SCHEMA_VERSION}"
                )
            self._create_schema()
            self.search_backend = self._create_search_index()
            self._backfill_search_index()
            if existing_version is None:
                self.set_metadata("schema_version", SCHEMA_VERSION)
            self.set_metadata("search_backend", self.search_backend)
            self.connection.commit()
        except Exception:
            self.connection.close()
            raise

    def close(self) -> None:
        self.connection.close()

    def _existing_schema_version(self) -> str | None:
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        names = {str(row[0]) for row in rows}
        if not names:
            return None
        if "metadata" not in names:
            raise SchemaVersionError("existing database has no schema_version metadata")
        row = self.connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        if row is None:
            raise SchemaVersionError("existing database has no schema_version value")
        return str(row[0])

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS favorites(
              id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
              summary TEXT NOT NULL, author_name TEXT, fav_time INTEGER NOT NULL,
              first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS favorite_lists(
              id INTEGER PRIMARY KEY, url_token TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
              first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS favorite_memberships(
              favorite_id INTEGER NOT NULL REFERENCES favorites(id),
              list_id INTEGER NOT NULL REFERENCES favorite_lists(id),
              first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
              PRIMARY KEY(favorite_id, list_id)
            );
            CREATE TABLE IF NOT EXISTS sync_runs(
              id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT NOT NULL,
              status TEXT NOT NULL, report_json TEXT NOT NULL
            );
            """
        )

    def _create_search_index(self) -> str:
        try:
            self.connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS favorites_fts USING fts5(favorite_id UNINDEXED, title, summary, tokenize='trigram')"
            )
            return "fts5-trigram"
        except sqlite3.OperationalError:
            return "like"

    def _backfill_search_index(self) -> None:
        if self.search_backend != "fts5-trigram":
            return
        favorite_count = int(self.connection.execute("SELECT count(*) FROM favorites").fetchone()[0])
        indexed_count = int(self.connection.execute("SELECT count(*) FROM favorites_fts").fetchone()[0])
        if favorite_count == indexed_count:
            return
        self.connection.execute("DELETE FROM favorites_fts")
        self.connection.execute(
            "INSERT INTO favorites_fts(favorite_id, title, summary) SELECT id, title, summary FROM favorites"
        )

    @contextmanager
    def sync_transaction(self) -> Iterator[SyncTransaction]:
        self.connection.execute("BEGIN IMMEDIATE")
        transaction = SyncTransaction(self)
        try:
            yield transaction
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def record_failed_sync(self, started_at: str, message: str) -> None:
        finished = utc_now()
        report = {"error": message}
        self.connection.execute(
            "INSERT INTO sync_runs(started_at, finished_at, status, report_json) VALUES (?, ?, 'failed', ?)",
            (started_at, finished, json.dumps(report, ensure_ascii=False)),
        )
        self.connection.commit()

    def set_metadata(self, key: str, value: str) -> None:
        self.connection.execute(
            "INSERT INTO metadata(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def get_metadata(self, key: str) -> str | None:
        row = self.connection.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def count_favorites(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM favorites").fetchone()[0])

    def get_favorite(self, url: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM favorites WHERE url=?", (url,)).fetchone()
        return None if row is None else dict(row)

    def memberships_for(self, url: str) -> list[str]:
        rows = self.connection.execute(
            """SELECT l.title FROM favorite_lists l
               JOIN favorite_memberships m ON m.list_id=l.id
               JOIN favorites f ON f.id=m.favorite_id WHERE f.url=? ORDER BY l.title""",
            (url,),
        ).fetchall()
        return [str(row[0]) for row in rows]

    def last_sync_run(self) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        return None if row is None else dict(row)

    def all_search_rows(
        self, candidate_ids: set[int] | None = None, list_terms: list[str] | None = None
    ) -> list[dict[str, Any]]:
        where = ""
        parameters: list[Any] = []
        if candidate_ids is not None:
            conditions: list[str] = []
            if candidate_ids:
                placeholders = ",".join("?" for _ in candidate_ids)
                conditions.append(f"f.id IN ({placeholders})")
                parameters.extend(sorted(candidate_ids))
            for term in list_terms or []:
                conditions.append(
                    "EXISTS (SELECT 1 FROM favorite_memberships mx "
                    "JOIN favorite_lists lx ON lx.id=mx.list_id "
                    "WHERE mx.favorite_id=f.id AND instr(lower(lx.title), lower(?)) > 0)"
                )
                parameters.append(term)
            if not conditions:
                return []
            where = "WHERE " + " OR ".join(conditions)
        rows = self.connection.execute(
            f"""SELECT f.*, GROUP_CONCAT(l.title, char(31)) AS list_titles
                FROM favorites f
                LEFT JOIN favorite_memberships m ON m.favorite_id=f.id
                LEFT JOIN favorite_lists l ON l.id=m.list_id
                {where}
                GROUP BY f.id""",
            parameters,
        ).fetchall()
        return [dict(row) for row in rows]

    def fts_candidate_ids(self, term: str) -> set[int]:
        if self.search_backend != "fts5-trigram":
            return set()
        phrase = '"' + term.replace('"', '""') + '"'
        try:
            rows = self.connection.execute(
                "SELECT favorite_id FROM favorites_fts WHERE favorites_fts MATCH ?", (phrase,)
            ).fetchall()
        except sqlite3.OperationalError:
            return set()
        return {int(row[0]) for row in rows}

    def status(self) -> dict[str, Any]:
        last_sync = self.get_metadata("last_successful_sync")
        warnings_raw = self.get_metadata("last_warnings") or "[]"
        try:
            warnings = json.loads(warnings_raw)
        except json.JSONDecodeError:
            warnings = ["INVALID_STORED_WARNING"]
        stale = False
        if last_sync:
            parsed = datetime.fromisoformat(last_sync)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            stale = (datetime.now(timezone.utc) - parsed).total_seconds() > 7 * 86400
        return {
            "indexed": bool(last_sync),
            "database_path": str(self.path.resolve()),
            "favorite_count": self.count_favorites(),
            "last_successful_sync": last_sync,
            "search_backend": self.search_backend,
            "stale": stale,
            "warnings": warnings,
        }
