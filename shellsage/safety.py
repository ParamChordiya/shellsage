"""Safety checks: hard blocklist and danger-level classification."""

from __future__ import annotations

BLOCKLIST: list[str] = [
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "rm -rf ~/",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    "dd if=/dev/urandom",
    "mkfs",
    "> /dev/sda",
    "chmod -R 777 /",
    ":(){ :|:& };:",
    "wget -O- | sh",
    "curl | sh",
    "curl | bash",
]

# Patterns whose presence raises the danger level to "destructive"
_DESTRUCTIVE_PATTERNS: list[str] = [
    "rm -rf",
    "rm -r ",
    "rm -f ",
    "dd if=",
    "mkfs",
    ":(){",
    "| sh",
    "| bash",
    "> /dev/",
    "chmod -R 777",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "format",
    "fdisk",
    "parted",
    "wipefs",
]

# Patterns that warrant a "caution" warning
_CAUTION_PATTERNS: list[str] = [
    "sudo",
    "rm ",
    "mv ",
    "chmod",
    "chown",
    "kill",
    "pkill",
    "killall",
    "truncate",
    "overwrite",
    "drop table",
    "delete from",
    "curl",
    "wget",
    "pip install",
    "npm install",
    "apt install",
    "brew install",
    "systemctl",
    "service ",
    "> ",   # output redirection (overwrite)
]


def is_blocked(command: str) -> bool:
    """Return True if *command* matches any hard-blocked pattern."""
    cmd_lower = command.lower().strip()
    for pattern in BLOCKLIST:
        if pattern.lower() in cmd_lower:
            return True
    return False


def classify_danger(command: str, llm_level: str = "safe") -> str:
    """Return the effective danger level for *command*.

    The LLM-provided *llm_level* is used as a starting point, but we
    always escalate to 'destructive' or 'caution' if our own patterns
    match, to guard against under-reporting.

    Returns one of: "safe", "caution", "destructive".
    """
    cmd_lower = command.lower()

    for pattern in _DESTRUCTIVE_PATTERNS:
        if pattern.lower() in cmd_lower:
            return "destructive"

    if llm_level == "destructive":
        return "destructive"

    for pattern in _CAUTION_PATTERNS:
        if pattern.lower() in cmd_lower:
            return "caution"

    if llm_level == "caution":
        return "caution"

    return "safe"


def danger_color(level: str) -> str:
    """Return the Rich border colour for the given danger level."""
    return {"safe": "green", "caution": "yellow", "destructive": "red"}.get(
        level, "white"
    )


def danger_emoji(level: str) -> str:
    """Return the status emoji for the given danger level."""
    return {"safe": "🟢", "caution": "🟡", "destructive": "🔴"}.get(level, "⚪")
