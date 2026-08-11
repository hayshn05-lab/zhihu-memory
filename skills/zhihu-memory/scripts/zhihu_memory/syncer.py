from __future__ import annotations

from typing import Any

from .storage import MemoryStore, utc_now


class SyncFailed(RuntimeError):
    pass


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _author_name(item: dict[str, Any]) -> str | None:
    author = item.get("Author")
    if isinstance(author, dict):
        value = author.get("Name") or author.get("name")
        return None if value is None else str(value)
    value = item.get("AuthorName")
    return None if value is None else str(value)


class SyncEngine:
    def __init__(self, store: MemoryStore, client: Any, page_size: int = 50, max_pages: int = 200):
        self.store = store
        self.client = client
        self.page_size = page_size
        self.max_pages = max_pages

    def run(self) -> dict[str, Any]:
        started = utc_now()
        report: dict[str, Any] = {
            "started_at": started,
            "api_calls": 0,
            "folder_count": 0,
            "raw_rows": 0,
            "unique_items": 0,
            "empty_pages": 0,
            "lists": [],
            "warnings": [],
        }
        seen_urls: set[str] = set()
        try:
            self.client.verify()
            report["api_calls"] += 1
            lists = self.client.favorite_lists(50)
            report["api_calls"] += 1
            report["folder_count"] = len(lists)
            if len(lists) == 50:
                report["warnings"].append("FOLDER_LIST_LIMIT_REACHED")
            with self.store.sync_transaction() as tx:
                for entry in lists:
                    token = _text(entry.get("UrlToken") or entry.get("url_token"))
                    title = _text(entry.get("Title") or entry.get("title") or token)
                    if not token:
                        raise ValueError("favorite list is missing UrlToken")
                    tx.upsert_list(token, title)
                    consecutive_empty = 0
                    page_count = 0
                    raw_for_list = 0
                    stop_reason = "page_cap"
                    for page_index in range(self.max_pages):
                        offset = page_index * self.page_size
                        items = self.client.favorite_items(token, offset, self.page_size)
                        report["api_calls"] += 1
                        page_count += 1
                        if not items:
                            report["empty_pages"] += 1
                            consecutive_empty += 1
                            if consecutive_empty == 2:
                                stop_reason = "two_empty_pages"
                                break
                            continue
                        consecutive_empty = 0
                        raw_for_list += len(items)
                        report["raw_rows"] += len(items)
                        for item in items:
                            url = _text(item.get("Url") or item.get("url"))
                            if not url:
                                continue
                            seen_urls.add(url)
                            tx.upsert_favorite(
                                url,
                                _text(item.get("Title") or item.get("title")),
                                _text(item.get("Summary") or item.get("summary")),
                                _author_name(item),
                                int(item.get("FavTime") or item.get("fav_time") or 0),
                                token,
                            )
                    if stop_reason == "page_cap":
                        report["warnings"].append("PAGE_CAP_REACHED")
                    report["lists"].append(
                        {
                            "url_token": token,
                            "title": title,
                            "pages": page_count,
                            "raw_rows": raw_for_list,
                            "stop_reason": stop_reason,
                        }
                    )
                report["unique_items"] = len(seen_urls)
                report["warnings"] = list(dict.fromkeys(report["warnings"]))
                tx.mark_success(report)
            return report
        except Exception as exc:
            self.store.record_failed_sync(started, str(exc))
            raise SyncFailed(str(exc)) from exc
