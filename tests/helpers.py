from __future__ import annotations

from dataclasses import dataclass, field


def favorite(url: str, title: str, summary: str = "", fav_time: int = 1_700_000_000, author=None):
    return {
        "Url": url,
        "Title": title,
        "Summary": summary,
        "FavTime": fav_time,
        "Author": author,
    }


@dataclass
class FakeClient:
    lists: list[dict]
    pages: dict[tuple[str, int], list[dict]]
    fail_at: tuple[str, int] | None = None
    calls: list[tuple] = field(default_factory=list)

    def verify(self):
        self.calls.append(("verify",))
        return {"ok": True, "installed": True, "auth": {"configured": True}}

    def favorite_lists(self, limit: int):
        self.calls.append(("lists", limit))
        return self.lists

    def favorite_items(self, token: str, offset: int, limit: int):
        self.calls.append(("items", token, offset, limit))
        if self.fail_at == (token, offset):
            raise RuntimeError("synthetic API failure")
        return self.pages.get((token, offset), [])
