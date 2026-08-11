---
name: zhihu-memory
description: Use when a user asks to recall, find, search, sync, refresh, or audit something previously saved in their own Zhihu favorites, especially an old answer or article remembered only by topic, date, collection, or a text fragment.
---

# Zhihu Memory

Use the bundled Python tool to search an auditable local snapshot of the current user's Zhihu favorites. Treat the official `zhihu-cli` as the account connector and keep credentials in its credential store.

Resolve relative paths against this Skill directory. Use Python 3.11 or newer:

```text
python scripts/zhihu_memory.py status
python scripts/zhihu_memory.py sync [--cli PATH]
python scripts/zhihu_memory.py search --term TERM [--term TERM ...] [--after YYYY-MM-DD] [--before YYYY-MM-DD] [--list NAME] [--limit 10]
```

## Find saved content

1. Run `status` once. If `indexed=false`, tell the user that the first lookup is creating a local snapshot, then run `sync`. The request to search their favorites authorizes this first initialization.
2. If an index exists, search it without refreshing. If it is older than seven days, return results and mention staleness; refresh only when the user asks.
3. Extract 2–6 distinctive terms from the memory: named entities, titles, domain terms, or remembered phrases. Map explicit dates and collection names to filters. Drop filler such as “以前”“好像”“帮我找”.
4. Run `search`. If it returns no candidates, broaden the terms once. Do not retry repeatedly.
5. Present the strongest candidates with title, saved date, collection, evidence snippet, and original URL. Include index time and coverage warnings when relevant.

## Refresh the snapshot

Run `sync` when the user explicitly asks to sync, refresh, or update. The tool scans fixed 50-item windows and stops only after two consecutive empty pages or its safety cap; it does not trust upstream `IsEnd`, `Totals`, or `NextOffset` values.

Describe the database as a best-effort local snapshot, never a complete backup. A successful sync can still omit deleted, inaccessible, unreturned, or undiscovered content. Do not delete local rows merely because a later sync did not return them.

## Evidence boundaries

- Say the user saved, collected, or previously followed the content. Do not infer endorsement, belief, or authorship.
- Do not mix public Zhihu search into personal results. If local search fails, report that result and offer public search as a separate next action.
- Do not expose or request the stored Access Secret. For `CLI_NOT_FOUND` or authentication errors, direct the user to install or configure the official Zhihu Skill/CLI.
- Stop on quota, rate-limit, invalid JSON, or sync errors. Preserve and report the last successful snapshot.

## Output contract

Lead with likely matches, not implementation details. Distinguish exact-looking matches from broader candidates, retain original links, and state uncertainty when coverage warnings or weak term matches apply.
