"""
In-memory session store for chat history.
Keyed by session_id (UUID string).
Stores last 20 messages per session.
"""

from collections import defaultdict

_sessions: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY = 20


def get_history(session_id: str) -> list[dict]:
    return _sessions[session_id]


def append_message(session_id: str, role: str, content: str):
    _sessions[session_id].append({"role": role, "content": content})
    # Keep only last MAX_HISTORY messages
    if len(_sessions[session_id]) > MAX_HISTORY:
        _sessions[session_id] = _sessions[session_id][-MAX_HISTORY:]


def clear_session(session_id: str):
    _sessions.pop(session_id, None)
