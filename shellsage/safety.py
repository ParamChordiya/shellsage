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
    # Dangerous find variants
    "find / -delete",
    "find /home -delete",
    "find / -exec rm",
    # Secure deletion
    "shred -u",
    # Truncating system paths
    "truncate -s 0 /etc",
    # History wiping
    "history -c",
    # Lock everyone out of root
    "chmod 000 /",
    # Pipe-to-interpreter patterns
    "| zsh",
    "| python",
    "| python3",
    "| perl",
    "| ruby",
]

# Substring patterns used to detect fork bombs (handled separately in is_blocked)
_FORK_BOMB_MARKERS: tuple[str, str] = ("(){", "|:")

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
    # Git operations that are hard to reverse
    "git push --force",
    "git push -f",
    "git reset --hard",
    "git clean -fd",
    "git clean -f",
    # Docker destructive operations
    "docker rm -f",
    "docker rmi -f",
    # Kubernetes deletions
    "kubectl delete",
]


def is_echo_wrapped(cmd: str) -> bool:
    """Return True if *cmd* is simply printing text via echo or printf.

    Commands that start with ``echo `` or ``printf `` are considered safe
    wrappers — the dangerous-looking content is just a string argument, not
    something that will be executed.
    """
    stripped = cmd.strip().lower()
    return stripped.startswith("echo ") or stripped.startswith("printf ")


def _normalize(cmd: str) -> str:
    """Collapse runs of whitespace/tabs so patterns can't be evaded by spacing."""
    return " ".join(cmd.lower().split())


def is_blocked(command: str) -> bool:
    """Return True if *command* matches any hard-blocked pattern.

    False-positive protection: commands that are merely *printing* dangerous
    strings (echo / printf wrappers) are allowed through.
    """
    # Printing a dangerous string is not itself dangerous
    if is_echo_wrapped(command):
        return False

    cmd_norm = _normalize(command)

    for pattern in BLOCKLIST:
        if _normalize(pattern) in cmd_norm:
            return True

    # Fork-bomb detection: look for both markers after normalization
    marker_a, marker_b = _FORK_BOMB_MARKERS
    if marker_a in cmd_norm and marker_b in cmd_norm:
        return True

    return False


def classify_danger(command: str, llm_level: str = "safe") -> str:
    """Return the effective danger level for *command*.

    The LLM-provided *llm_level* is used as a starting point, but we
    always escalate to 'destructive' or 'caution' if our own patterns
    match, to guard against under-reporting.

    Returns one of: "safe", "caution", "destructive".
    """
    cmd_norm = _normalize(command)

    for pattern in _DESTRUCTIVE_PATTERNS:
        if _normalize(pattern) in cmd_norm:
            return "destructive"

    if llm_level == "destructive":
        return "destructive"

    for pattern in _CAUTION_PATTERNS:
        if _normalize(pattern) in cmd_norm:
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
