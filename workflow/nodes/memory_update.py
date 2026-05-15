"""Session-memory update node."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


def memory_update_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Append the latest exchange to the in-memory conversation history."""
    history_entry = {
        "user": state.get("user_message", ""),
        "assistant": state.get("commentary", ""),
        "query_plan": state.get("query_plan", {}),
        "timestamp": datetime.now().isoformat(),
    }
    state.setdefault("history", []).append(history_entry)
    return state
