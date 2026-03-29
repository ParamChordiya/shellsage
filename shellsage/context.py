"""Detect runtime context: OS, shell, cwd, and installed tools."""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, field

_TOOLS_TO_CHECK = [
    "git", "docker", "kubectl", "python3", "pip",
    "npm", "node", "brew", "apt", "yum",
    "ffmpeg", "jq", "curl", "wget", "rsync",
    "tar", "zip", "unzip",
]


@dataclass
class ShellContext:
    """Snapshot of the user's current shell environment."""

    os_name: str
    shell: str
    cwd: str
    tools: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "os": self.os_name,
            "shell": self.shell,
            "cwd": self.cwd,
            "tools": self.tools,
        }


def get_context() -> ShellContext:
    """Collect and return the current shell context."""
    return ShellContext(
        os_name=_detect_os(),
        shell=_detect_shell(),
        cwd=os.getcwd(),
        tools=_detect_tools(),
    )


def _detect_os() -> str:
    system = platform.system()
    mapping = {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}
    return mapping.get(system, system)


def _detect_shell() -> str:
    shell = os.environ.get("SHELL") or os.environ.get("COMSPEC") or "unknown"
    # Return just the binary name for brevity (e.g. "zsh" not "/bin/zsh")
    return os.path.basename(shell)


def _detect_tools() -> list[str]:
    return [tool for tool in _TOOLS_TO_CHECK if shutil.which(tool) is not None]
