"""Session persistence for ShellSage chat mode.

Sessions are stored as JSON files under ~/.shellsage/sessions/.
All disk operations are best-effort — failures are silently swallowed so
that a missing or unwritable sessions directory never breaks the REPL.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path.home() / ".shellsage" / "sessions"


def get_sessions_dir() -> Path:
    """Return the sessions directory, creating it if necessary."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def new_session_id() -> str:
    """Generate a human-readable, time-ordered session ID."""
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]


def _session_path(session_id: str) -> Path:
    # Bug fix: a user-supplied session_id like "../../etc/passwd" would escape
    # the sessions directory.  Resolve the candidate path and verify it stays
    # inside SESSIONS_DIR before returning it.
    candidate = (SESSIONS_DIR / f"{session_id}.json").resolve()
    sessions_root = SESSIONS_DIR.resolve()
    if not str(candidate).startswith(str(sessions_root) + os.sep):
        raise ValueError(f"Invalid session ID: {session_id!r}")
    return candidate


def _first_user_message(messages: list) -> str:
    """Return the first user message content, truncated to 80 characters."""
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            return content[:80] + ("..." if len(content) > 80 else "")
    return ""


def save_session(session_id: str, messages: list, metadata: dict | None = None) -> None:
    """Save session messages to disk. Silent on failure."""
    try:
        sessions_dir = get_sessions_dir()
        path = sessions_dir / f"{session_id}.json"

        now = datetime.now().isoformat(timespec="seconds")

        # Preserve created_at if the file already exists
        created_at = now
        if path.exists():
            try:
                existing = json.loads(path.read_text())
                created_at = existing.get("created_at", now)
            except Exception:
                pass

        data = {
            "id": session_id,
            "created_at": created_at,
            "updated_at": now,
            "message_count": len(messages),
            "preview": _first_user_message(messages),
            "messages": messages,
        }
        if metadata:
            data.update(metadata)

        # Bug fix: write to a temp file in the same directory, then atomically
        # rename it into place.  A crash during the write previously left a
        # truncated (corrupt) session file, making the session unresumable.
        tmp_fd, tmp_path = tempfile.mkstemp(dir=sessions_dir, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, indent=2, ensure_ascii=False))
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception:
        pass  # best-effort; never break the REPL


def load_session(session_id: str) -> list | None:
    """Load session messages from disk. Returns None if not found or unreadable."""
    try:
        path = _session_path(session_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return data.get("messages")
    except Exception:
        return None


def list_sessions() -> list[dict]:
    """Return a list of session metadata dicts, newest first."""
    try:
        sessions_dir = get_sessions_dir()
    except Exception:
        return []

    sessions: list[dict] = []
    for path in sessions_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            sessions.append({
                "id": data.get("id", path.stem),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "message_count": data.get("message_count", 0),
                "preview": data.get("preview", ""),
            })
        except Exception:
            continue

    # Sort newest first by created_at (ISO string — lexicographic sort works)
    sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return sessions


def delete_session(session_id: str) -> bool:
    """Delete a session file. Returns True if deleted, False if not found."""
    try:
        path = _session_path(session_id)
        if not path.exists():
            return False
        path.unlink()
        return True
    except Exception:
        return False
