"""Narration node for result commentary."""

from typing import Dict, Any
import json

NARRATE_SYSTEM_PROMPT = """
You are a professional stock-market analyst. Your task is to interpret query results in English.

Requirements:
1. Ground the explanation in the provided data only.
2. Do not invent figures.
3. Use clear professional language.
4. Keep it concise unless the user asks for more detail.

Important: do not perform new calculations; all numbers must come from the provided result.
Translate any stock names into English if the result contains non-English names.
"""


def narrate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Add a concise English commentary to the workflow state."""

    user_message = state.get("user_message", "")
    table = state.get("table", [])
    summary = state.get("summary", {})

    prompt = f"""
{NARRATE_SYSTEM_PROMPT}

User question:
{user_message}

Query result ({len(table)} rows shown):
{json.dumps(table, ensure_ascii=False, indent=2)}

Summary:
{json.dumps(summary, ensure_ascii=False, indent=2)}

Write a professional interpretation in English, 3-5 sentences:
"""

    state.setdefault("debug", {})["narrate_prompt"] = prompt
    row_count = summary.get("row_count", 0)
    state["commentary"] = f"Query complete. Returned {row_count} rows. The detailed data is shown above."

    return state
