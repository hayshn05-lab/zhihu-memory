from __future__ import annotations

import os
import platform
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("ZHIHU_MEMORY_HOME")
    if override:
        return Path(override).expanduser()
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "ZhihuMemory"
        return Path.home() / "AppData" / "Local" / "ZhihuMemory"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "zhihu-memory"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "zhihu-memory"


def database_path() -> Path:
    return data_dir() / "memory.sqlite3"
