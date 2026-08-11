from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any

from .storage import MemoryStore


def _date_timestamp(value: str, end_of_day: bool = False, zone: tzinfo | None = None) -> int:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    boundary = parsed + timedelta(days=1) if end_of_day else parsed
    if zone is not None:
        boundary = boundary.replace(tzinfo=zone)
    timestamp = int(boundary.timestamp())
    return timestamp - 1 if end_of_day else timestamp


def _local_date(timestamp: int, zone: tzinfo | None = None) -> str | None:
    if not timestamp:
        return None
    instant = datetime.fromtimestamp(timestamp, timezone.utc)
    localized = instant.astimezone(zone) if zone is not None else instant.astimezone()
    return localized.date().isoformat()


def _snippet(title: str, summary: str, terms: list[str], limit: int = 240) -> str:
    source = summary or title
    lowered = source.casefold()
    positions = [lowered.find(term.casefold()) for term in terms]
    positions = [position for position in positions if position >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - 60)
    text = source[start : start + limit]
    if start:
        text = "…" + text[1:]
    if start + limit < len(source):
        text = text[:-1] + "…"
    return text


class SearchEngine:
    def __init__(self, store: MemoryStore):
        self.store = store

    def search(
        self,
        terms: list[str],
        *,
        after: str | None = None,
        before: str | None = None,
        list_name: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        normalized = list(dict.fromkeys(term.strip() for term in terms if term.strip()))
        if not normalized:
            return []
        fts_ids: set[int] = set()
        has_short_term = False
        for term in normalized:
            if len(term) < 3:
                has_short_term = True
            else:
                fts_ids.update(self.store.fts_candidate_ids(term))
        after_ts = _date_timestamp(after) if after else None
        before_ts = _date_timestamp(before, end_of_day=True) if before else None
        results: list[dict[str, Any]] = []
        for row in self.store.all_search_rows():
            lists = [name for name in (row.get("list_titles") or "").split(chr(31)) if name]
            if list_name and not any(list_name.casefold() in name.casefold() for name in lists):
                continue
            if after_ts is not None and int(row["fav_time"]) < after_ts:
                continue
            if before_ts is not None and int(row["fav_time"]) > before_ts:
                continue
            if self.store.search_backend == "fts5-trigram" and not has_short_term and row["id"] not in fts_ids:
                if not any(term.casefold() in " ".join(lists).casefold() for term in normalized):
                    continue
            title = str(row["title"])
            summary = str(row["summary"])
            title_folded = title.casefold()
            summary_folded = summary.casefold()
            list_folded = " ".join(lists).casefold()
            score = 0
            matched: list[str] = []
            for term in normalized:
                folded = term.casefold()
                matched_this = False
                if folded in title_folded:
                    score += 12
                    matched_this = True
                if folded in summary_folded:
                    score += 4
                    matched_this = True
                if folded in list_folded:
                    score += 3
                    matched_this = True
                if matched_this:
                    matched.append(term)
            if not matched:
                continue
            fav_time = int(row["fav_time"])
            results.append(
                {
                    "title": title,
                    "author": row["author_name"],
                    "url": row["url"],
                    "fav_time": fav_time,
                    "fav_date": _local_date(fav_time),
                    "lists": sorted(lists),
                    "matched_terms": matched,
                    "snippet": _snippet(title, summary, matched),
                    "score": score,
                }
            )
        results.sort(key=lambda item: (-item["score"], -item["fav_time"], item["url"]))
        return results[:limit]
