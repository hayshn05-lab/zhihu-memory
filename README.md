# zhihu-memory

An installable [Agent Skill](https://agentskills.io/) that builds an auditable local snapshot of your Zhihu favorites and searches it deterministically.

It uses the official `zhihu-cli` as the authenticated account connector. It does not scrape pages, copy credentials, call embedding services, or treat a saved item as an endorsed opinion.

## Why it exists

The official personal-favorites API provides access, but its paging metadata can be inconsistent. `zhihu-memory` scans fixed windows, preserves cross-collection membership, deduplicates by URL, records coverage warnings, and keeps a reusable SQLite index.

This is a best-effort snapshot, not a complete backup. Deleted, inaccessible, unreturned, or undiscovered favorites can still be absent.

## Requirements

- Python 3.11 or newer; no third-party Python packages.
- The official Zhihu Skill/CLI installed and authenticated.
- Windows, macOS, or Linux.

The CLI binary is resolved from `--cli`, `ZHIHU_CLI_BIN`, `ZHIHU_CLI_HOME`, then the official default install directory.

## Install

Clone this repository, then copy `skills/zhihu-memory` into a skill directory recognized by your client.

Cross-client project install:

```text
<project>/.agents/skills/zhihu-memory/
```

User-level examples:

| Client | Install directory |
|---|---|
| Codex and compatible clients | `~/.agents/skills/zhihu-memory/` |
| Claude Code | `~/.claude/skills/zhihu-memory/` |
| Cursor | `~/.cursor/skills/zhihu-memory/` |

The neutral `.agents/skills` convention and portable package layout follow the [Agent Skills client guidance](https://agentskills.io/client-implementation/adding-skills-support). Cursor users can use `.cursor/skills` for reliable slash-menu discovery.

Restart the client after copying the Skill if it does not rescan skills dynamically.

## Use

Ask naturally:

```text
I remember saving something about PostgreSQL MVCC. Find it in my Zhihu favorites.
Refresh my Zhihu favorites index.
Find economics study materials I saved before 2024.
```

The deterministic script can also be run directly:

```bash
python skills/zhihu-memory/scripts/zhihu_memory.py status
python skills/zhihu-memory/scripts/zhihu_memory.py sync
python skills/zhihu-memory/scripts/zhihu_memory.py search --term 乡土中国 --term 费孝通 --limit 10
```

Operational commands emit JSON, including argument and storage errors; `--help` prints human-readable usage. `search` also accepts `--after`, `--before`, and `--list`.

## Local data

The database is stored outside the Skill so upgrades do not overwrite it:

- Windows: `%LOCALAPPDATA%\ZhihuMemory\memory.sqlite3`
- macOS: `~/Library/Application Support/zhihu-memory/memory.sqlite3`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/zhihu-memory/memory.sqlite3`

Set `ZHIHU_MEMORY_HOME` to override the data directory. The database contains favorite metadata and sync audit records, never the Access Secret.
On POSIX systems, the data directory and database are enforced as owner-only (`0700` and `0600`).

## Develop

```powershell
$env:PYTHONPATH="$PWD\skills\zhihu-memory\scripts"
python -m unittest discover -s tests -v
python -m py_compile skills\zhihu-memory\scripts\zhihu_memory.py
```

Automated tests use only synthetic data. A real-account smoke test must use a separate, ignored data directory and must never persist its output in the repository.

## License

MIT
