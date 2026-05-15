"""LLM-based query planner for HK and US daily stock data."""

from typing import Dict, Any, Optional, List, Tuple
import json
import re
from datetime import datetime, timedelta

from core.llm_client import LLMClient

FIELD_SCHEMA = {
    "Market": ("string", "Market code: HK or US"),
    "MDDate": ("string", "Trading date in YYYYMMDD format"),
    "SecurityID": ("string", "Ticker or local stock code"),
    "Symbol": ("string", "English stock display name"),
    "HTSCSecurityID": ("string", "Full code, such as 00700.HK or AAPL.US"),
    "PreClosePx": ("double", "Previous close"),
    "LastPx": ("double", "Latest close"),
    "OpenPx": ("double", "Open price"),
    "ClosePx": ("double", "Close price"),
    "HighPx": ("double", "High price"),
    "LowPx": ("double", "Low price"),
    "TotalVolumeTrade": ("double", "Daily volume"),
    "TotalValueTrade": ("double", "Daily traded value"),
    "ChangePx": ("double", "Price change"),
    "ChangePct": ("double", "Percent change"),
    "Amplitude": ("double", "Amplitude percentage"),
    "TurnoverRate": ("double", "Turnover-rate percentage"),
}

BASE_FIELDS = {k: v[1] for k, v in FIELD_SCHEMA.items()}

DERIVED_METRICS = {
    "GainPct": "ChangePct",
    "LossPct": "-ChangePct",
}

ALL_ALLOWED_FIELDS = set(BASE_FIELDS.keys()) | set(DERIVED_METRICS.keys())
ALLOWED_OPERATORS = {">", "<", "=", ">=", "<=", "!=", "LIKE", "IN", "BETWEEN"}
ALLOWED_AGG_FUNCS = {"SUM", "AVG", "COUNT", "MAX", "MIN", "STDDEV", "VARIANCE"}


# ============================================================================
# ============================================================================

PLANNER_SYSTEM_PROMPT = """You are a stock-market query planner. Convert the user's English natural-language question into a structured QueryPlan JSON object.

## Query Types

1. Data queries: rankings, filters, historical price series, and aggregate summaries.
   Return query_type "basic", "filter", "raw_data", or "stats".

2. Chat / concept questions: general explanations that do not need data.
   Return query_type "chat" and put the English answer in the "answer" field.

## Available Data

The current real dataset contains HK and US historical daily bars, one parquet file per stock. It is not intraday order-book data.

Fields:
- Market: HK or US
- MDDate: trading date, YYYYMMDD
- SecurityID: stock code, e.g. 00700 or AAPL
- Symbol: English stock display name when available
- HTSCSecurityID: full code, e.g. 00700.HK or AAPL.US
- OpenPx, ClosePx, LastPx, HighPx, LowPx, PreClosePx
- TotalVolumeTrade: daily volume
- TotalValueTrade: daily traded value / turnover amount
- ChangePx: price change
- ChangePct: daily percent change
- Amplitude: daily amplitude percentage
- TurnoverRate: turnover-rate percentage

Derived metrics:
- GainPct: ChangePct
- LossPct: -ChangePct

Markets:
- HK: Hong Kong stocks
- US: US stocks
- ALL: HK + US

Important constraints:
- Output JSON only. No markdown, no prose.
- Use YYYYMMDD dates.
- If the user does not specify an exact date, use the provided default date.
- If the user does not specify a market, use the provided default market.
- HK/US data has no limit-up/limit-down or order-book fields. Do not generate plans for those concepts.
- For historical price/trend questions, use query_type "raw_data", date_range, order by MDDate ascending, and include ClosePx.
- Always include SecurityID and Symbol for stock-level output. Include Market when market may be ALL.
- Any Chinese stock names returned by the raw data must be translated to English before final display or narration.

Output shape:
{
  "intent": "short English description",
  "date": "YYYYMMDD",
  "market": "HK/US/ALL",
  "query_type": "basic/filter/raw_data/stats/chat",
  "select_fields": ["Market", "SecurityID", "Symbol", "..."],
  "metrics": [],
  "filters": [{"field": "field or derived metric", "op": ">", "value": 10}],
  "order_by": [{"field": "field or derived metric", "desc": true}],
  "group_by": [],
  "aggregations": [{"func": "COUNT", "field": "*", "alias": "Total Count"}],
  "limit": 100
}
"""

FEW_SHOT_EXAMPLES = """
## Examples

User: Which HK stocks had the highest turnover today?
{
  "intent": "Rank HK stocks by daily traded value",
  "date": "20250115",
  "market": "HK",
  "query_type": "basic",
  "select_fields": ["Market", "SecurityID", "Symbol", "TotalValueTrade", "ClosePx"],
  "metrics": [],
  "filters": [],
  "order_by": [{"field": "TotalValueTrade", "desc": true}],
  "limit": 10
}

User: Show the 10 biggest US stock decliners today
{
  "intent": "Rank US stocks by worst daily percent change",
  "date": "20250115",
  "market": "US",
  "query_type": "basic",
  "select_fields": ["Market", "SecurityID", "Symbol", "ClosePx", "ChangePct"],
  "metrics": [],
  "filters": [],
  "order_by": [{"field": "ChangePct", "desc": false}],
  "limit": 10
}

User: Which stocks have turnover rate above 5% today?
{
  "intent": "Filter stocks by turnover rate above 5 percent",
  "date": "20250115",
  "market": "ALL",
  "query_type": "filter",
  "select_fields": ["Market", "SecurityID", "Symbol", "ClosePx", "TurnoverRate"],
  "metrics": [],
  "filters": [{"field": "TurnoverRate", "op": ">", "value": 5}],
  "order_by": [{"field": "TurnoverRate", "desc": true}],
  "limit": 100
}

User: Show Tesla's price trend in January 2025
{
  "intent": "Show Tesla daily price trend in January 2025",
  "market": "US",
  "query_type": "raw_data",
  "select_fields": ["Market", "SecurityID", "Symbol", "MDDate", "OpenPx", "ClosePx", "HighPx", "LowPx", "TotalVolumeTrade", "TotalValueTrade"],
  "metrics": [],
  "filters": [{"field": "SecurityID", "op": "=", "value": "TSLA"}],
  "date_range": {"start": "20250101", "end": "20250131"},
  "order_by": [{"field": "MDDate", "desc": false}],
  "limit": 1000
}

User: How many stocks rose and fell today?
{
  "intent": "Count rising and falling stocks",
  "date": "20250115",
  "market": "ALL",
  "query_type": "stats",
  "select_fields": [],
  "metrics": [],
  "aggregations": [
    {"func": "COUNT", "field": "CASE WHEN ChangePct > 0 THEN 1 END", "alias": "Rising Count"},
    {"func": "COUNT", "field": "CASE WHEN ChangePct < 0 THEN 1 END", "alias": "Falling Count"},
    {"func": "COUNT", "field": "*", "alias": "Total Count"}
  ],
  "limit": 1
}

User: What does percent change mean?
{
  "intent": "Explain percent change",
  "query_type": "chat",
  "answer": "Percent change is the stock's price movement compared with the previous close, expressed as a percentage. Positive values mean the stock rose; negative values mean it fell."
}
"""


class LLMQueryPlanner:
    """Generate and validate QueryPlans from natural-language questions."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize the planner."""
        self.llm_client = llm_client or LLMClient()

    def generate_plan(
        self,
        user_query: str,
        default_date: Optional[str] = None,
        default_market: str = "ALL",
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Generate a QueryPlan and validation errors from a user question."""

        # If no default date is provided, use yesterday as a fallback.
        if not default_date:
            yesterday = datetime.now() - timedelta(days=1)
            default_date = yesterday.strftime("%Y%m%d")

        prompt = self._build_prompt(user_query, default_date, default_market, context)

        try:
            response = self.llm_client.chat(
                prompt=prompt,
                system_prompt=PLANNER_SYSTEM_PROMPT,
                temperature=1,
                max_tokens=1024,
            )

            query_plan = self._parse_json_response(response)

            query_plan = self._apply_query_hints(query_plan, user_query)

            validation_errors = self._validate_plan(query_plan)

            query_plan = self._apply_defaults(query_plan, default_date, default_market)

            return query_plan, validation_errors

        except Exception as e:
            return {
                "error": str(e),
                "intent": "Planning failed",
                "date": default_date,
                "market": default_market,
            }, [f"LLM call or JSON parsing failed: {str(e)}"]

    def _apply_query_hints(self, plan: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """Apply conservative deterministic hints for common English/Chinese market wording."""
        query_lower = user_query.lower()
        plan_text = json.dumps(plan, ensure_ascii=False).lower()
        is_count_query = any(term in query_lower for term in ["how many", "count", "number of"])

        padded_query = f" {query_lower} "

        if "hong kong" in query_lower or re.search(r"\bhk\b", query_lower):
            plan["market"] = "HK"
        elif " us " in padded_query or any(term in query_lower for term in ["u.s.", "usa", "nasdaq", "nyse", "american"]):
            plan["market"] = "US"

        alias_filters = {
            "tesla": ("US", "SecurityID", "TSLA"),
            "apple": ("US", "SecurityID", "AAPL"),
            "nvidia": ("US", "SecurityID", "NVDA"),
            "microsoft": ("US", "SecurityID", "MSFT"),
            "amazon": ("US", "SecurityID", "AMZN"),
            "tencent": ("HK", "SecurityID", "00700"),
            "alibaba": ("HK", "SecurityID", "09988"),
        }

        for alias, (market, field, value) in alias_filters.items():
            if alias in query_lower:
                plan["market"] = market
                filters = [f for f in plan.get("filters", []) if f.get("field") not in {"Symbol", "SecurityID"}]
                filters.append({"field": field, "op": "=", "value": value})
                plan["filters"] = filters
                break

        month_match = re.search(
            r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})",
            query_lower,
        )
        if month_match and any(word in query_lower for word in ["trend", "history", "historical", "price"]):
            month_names = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12,
            }
            month = month_names[month_match.group(1)]
            year = int(month_match.group(2))
            if month == 12:
                next_year, next_month = year + 1, 1
            else:
                next_year, next_month = year, month + 1
            end = datetime(next_year, next_month, 1) - timedelta(days=1)
            plan["query_type"] = "raw_data"
            plan["date_range"] = {
                "start": f"{year}{month:02d}01",
                "end": end.strftime("%Y%m%d"),
            }
            plan["select_fields"] = [
                "Market", "SecurityID", "Symbol", "MDDate", "OpenPx", "ClosePx",
                "HighPx", "LowPx", "TotalVolumeTrade", "TotalValueTrade",
            ]
            plan["metrics"] = []
            plan["order_by"] = [{"field": "MDDate", "desc": False}]
            plan["limit"] = max(plan.get("limit", 1000), 1000)

        if is_count_query and any(term in query_lower for term in ["rose", "rising", "fell", "falling", "declined", "decliners"]):
            plan["query_type"] = "stats"
            plan["select_fields"] = []
            plan["metrics"] = []
            plan["filters"] = []
            plan["order_by"] = []
            plan["aggregations"] = [
                {"func": "COUNT", "field": "CASE WHEN ChangePct > 0 THEN 1 END", "alias": "RisingCount"},
                {"func": "COUNT", "field": "CASE WHEN ChangePct < 0 THEN 1 END", "alias": "FallingCount"},
                {"func": "COUNT", "field": "*", "alias": "TotalCount"},
            ]
            plan["limit"] = 1

        if any(term in query_lower for term in ["turnover rate", "turnover-rate"]):
            plan["select_fields"] = ["Market", "SecurityID", "Symbol", "ClosePx", "TurnoverRate"]
            plan["metrics"] = []
            plan["order_by"] = [{"field": "TurnoverRate", "desc": True}]
            if any(term in query_lower for term in ["above", "over", "greater", ">"]):
                plan["query_type"] = "filter"
            else:
                plan.setdefault("query_type", "basic")
            percent_match = re.search(r"(?:above|over|greater than|>)\s*(\d+(?:\.\d+)?)\s*%?", query_lower)
            if percent_match and "turnoverrate" not in plan_text:
                plan["filters"] = plan.get("filters", [])
                plan["filters"].append({"field": "TurnoverRate", "op": ">", "value": float(percent_match.group(1))})

        elif any(term in query_lower for term in ["turnover", "traded value", "trading value", "amount"]):
            plan["select_fields"] = ["Market", "SecurityID", "Symbol", "ClosePx", "TotalValueTrade"]
            plan["metrics"] = plan.get("metrics", [])
            plan["order_by"] = [{"field": "TotalValueTrade", "desc": True}]
            plan.setdefault("limit", 10)
            plan.setdefault("query_type", "basic")

        if not is_count_query and any(term in query_lower for term in ["decliner", "decliners", "loser", "losers", "fell", "fall", "down", "biggest drops"]):
            plan["select_fields"] = ["Market", "SecurityID", "Symbol", "ClosePx", "ChangePct"]
            plan["metrics"] = []
            plan["order_by"] = [{"field": "ChangePct", "desc": False}]
            plan.setdefault("query_type", "basic")

        if not is_count_query and any(term in query_lower for term in ["gainer", "gainers", "rose", "riser", "risers", "up", "highest gain"]):
            plan["select_fields"] = ["Market", "SecurityID", "Symbol", "ClosePx", "ChangePct"]
            plan["metrics"] = []
            plan["order_by"] = [{"field": "ChangePct", "desc": True}]
            plan.setdefault("query_type", "basic")

        limit_match = re.search(r"\b(?:top|highest|biggest|largest|show)(?:\s+the)?\s+(\d+)\b", query_lower)
        if limit_match:
            plan["limit"] = int(limit_match.group(1))

        return plan

    def _build_prompt(
        self,
        user_query: str,
        default_date: str,
        default_market: str,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Build the LLM prompt."""

        prompt_parts = [FEW_SHOT_EXAMPLES]

        if context:
            prompt_parts.append(f"\n## Conversation Context\n{json.dumps(context, ensure_ascii=False)}")

        prompt_parts.append(f"""
## Current Query

Default date: {default_date}
Default market: {default_market}
User input: {user_query}

Return QueryPlan JSON only:
""")

        return "\n".join(prompt_parts)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from an LLM response."""

        response = response.strip()

        if response.startswith("```"):
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if match:
                response = match.group(1)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                return json.loads(match.group(0))
            raise ValueError(f"Could not parse JSON from response: {response[:200]}...")

    def _validate_plan(self, plan: Dict[str, Any]) -> List[str]:
        """
        Validate the query plan for allowed fields and operators.
        """
        errors = []

        date_str = plan.get("date")
        if date_str:
            try:
                datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                errors.append(f"Invalid date format (expected YYYYMMDD): {date_str}")

        market = plan.get("market")
        if market and market not in {"HK", "US", "ALL"}:
            errors.append(f"Invalid market code: {market}")

        limit = plan.get("limit")
        if limit is not None:
            if not isinstance(limit, int) or limit < 1 or limit > 10000:
                errors.append(f"limit must be an integer from 1 to 10000: {limit}")

        for field in plan.get("select_fields", []):
            if field not in ALL_ALLOWED_FIELDS:
                errors.append(f"Field is not allowed: {field}")

        for metric in plan.get("metrics", []):
            if metric not in DERIVED_METRICS:
                errors.append(f"Metric is not allowed: {metric}")

        for f in plan.get("filters", []):
            field = f.get("field")
            op = f.get("op", "").upper()
            if field and field not in ALL_ALLOWED_FIELDS:
                errors.append(f"Filter field is not allowed: {field}")
            if op and op not in ALLOWED_OPERATORS:
                errors.append(f"Operator is not allowed: {op}")

        for o in plan.get("order_by", []):
            field = o.get("field")
            if field and field not in ALL_ALLOWED_FIELDS:
                errors.append(f"Sort field is not allowed: {field}")

        for field in plan.get("group_by", []):
            if field not in ALL_ALLOWED_FIELDS:
                errors.append(f"Group-by field is not allowed: {field}")

        return errors

    def _apply_defaults(
        self,
        plan: Dict[str, Any],
        default_date: str,
        default_market: str,
    ) -> Dict[str, Any]:
        """Apply default values to the plan."""

        if "date" not in plan or not plan["date"]:
            plan["date"] = default_date

        if "market" not in plan or not plan["market"]:
            plan["market"] = default_market

        if "limit" not in plan or not plan["limit"]:
            plan["limit"] = 100

        if "select_fields" not in plan:
            plan["select_fields"] = ["SecurityID"]

        if "metrics" not in plan:
            plan["metrics"] = []

        if "filters" not in plan:
            plan["filters"] = []

        if "order_by" not in plan:
            plan["order_by"] = []

        return plan


def generate_query_plan(
    user_query: str,
    default_date: Optional[str] = None,
    default_market: str = "ALL",
    llm_client: Optional[LLMClient] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Generate a query plan from a natural-language question.
    """
    planner = LLMQueryPlanner(llm_client)
    return planner.generate_plan(user_query, default_date, default_market)


if __name__ == "__main__":
    print("LLM query planner test")
    print("=" * 60)

    planner = LLMQueryPlanner()

    test_queries = [
        "Which HK stocks had the highest turnover today?",
        "Show the 10 biggest US stock decliners today",
        "How many stocks rose and fell today?",
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 40)
        try:
            plan, errors = planner.generate_plan(query)
            print(f"Plan: {json.dumps(plan, ensure_ascii=False, indent=2)}")
            if errors:
                print(f"Errors: {errors}")
        except Exception as e:
            print(f"Error: {e}")
            break
