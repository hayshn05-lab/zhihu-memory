from __future__ import annotations

import os
import platform
from pathlib import Path


class CliNotFound(RuntimeError):
    pass


def default_candidates() -> list[Path]:
    system = platform.system()
    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return [base / "ZhihuCLI" / "current" / "zhihu-cli.exe"]
    if system == "Darwin":
        return [Path.home() / "Library" / "Application Support" / "zhihu-cli" / "current" / "zhihu-cli"]
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    linux_base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return [
        linux_base / "zhihu-cli" / "current" / "zhihu-cli",
        Path.home() / "Library" / "Application Support" / "zhihu-cli" / "current" / "zhihu-cli",
    ]


def locate_cli(explicit: str | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env_binary = os.environ.get("ZHIHU_CLI_BIN")
    if env_binary:
        candidates.append(Path(env_binary).expanduser())
    cli_home = os.environ.get("ZHIHU_CLI_HOME")
    if cli_home:
        suffix = "zhihu-cli.exe" if platform.system() == "Windows" else "zhihu-cli"
        candidates.append(Path(cli_home).expanduser() / "current" / suffix)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    for candidate in default_candidates():
        if candidate.is_file():
            return candidate.resolve()
    raise CliNotFound(
        "Official zhihu-cli was not found. Set ZHIHU_CLI_BIN, set ZHIHU_CLI_HOME, "
        "or install the official Zhihu Skill/CLI first."
    )
