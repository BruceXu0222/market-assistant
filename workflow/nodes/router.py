"""Rule-based router node for workflow state."""

from typing import Dict, Any


MARKET_QUERY_KEYWORDS = [
    "stock", "stocks", "market", "gainer", "gainers", "decliner", "decliners",
    "loser", "losers", "turnover", "volume", "price", "trend", "highest",
    "lowest", "top", "rank", "ranking", "filter", "amplitude", "traded value",
]

FIELD_EXPLAIN_KEYWORDS = [
    "what is", "what does", "meaning", "explain", "definition", "field",
]

CHITCHAT_KEYWORDS = [
    "hello", "hi", "thanks", "thank you", "bye", "help", "who are you",
]


def router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Set query_type for a user message."""

    user_message = state.get("user_message", "")

    if any(keyword in user_message for keyword in FIELD_EXPLAIN_KEYWORDS):
        state["query_type"] = "field_explain"
        return state

    if any(keyword in user_message for keyword in CHITCHAT_KEYWORDS):
        state["query_type"] = "chitchat"
        state["commentary"] = "Hello. I can help analyze HK and US daily stock data. What would you like to query?"
        return state

    if any(keyword in user_message for keyword in MARKET_QUERY_KEYWORDS):
        state["query_type"] = "market_query"
        return state

    state["query_type"] = "market_query"
    return state
