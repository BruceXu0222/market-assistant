"""Repair node for invalid QueryPlans."""

from typing import Dict, Any
import json

REPAIR_SYSTEM_PROMPT = """
You are a QueryPlan repair assistant. Fix the QueryPlan according to validation errors.

Repair rules:
1. Only fix the issues mentioned in the errors.
2. Follow the allowed fields and business rules.
3. Output valid JSON.
4. Output the repaired QueryPlan only, with no extra prose.

Allowed fields:
- Market, MDDate, SecurityID, Symbol, HTSCSecurityID
- OpenPx, ClosePx, HighPx, LowPx, PreClosePx, LastPx
- TotalValueTrade, TotalVolumeTrade, ChangePx, ChangePct, Amplitude, TurnoverRate
- GainPct, LossPct

Allowed markets: HK, US, ALL
Allowed operators: >, <, =, >=, <=, !=
"""


def repair_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Attempt a conservative repair of an invalid QueryPlan."""

    query_plan = state.get("query_plan")
    validation_errors = state.get("validation_errors", [])

    prompt = f"""
{REPAIR_SYSTEM_PROMPT}

Original QueryPlan:
{json.dumps(query_plan, ensure_ascii=False, indent=2)}

Validation errors:
{chr(10).join(f"- {error}" for error in validation_errors)}

Return the repaired QueryPlan as JSON only:
"""

    state.setdefault("debug", {})["repair_prompt"] = prompt
    response = json.dumps(query_plan, ensure_ascii=False)

    try:
        repaired_plan = json.loads(response)
        state["query_plan"] = repaired_plan
        state["validation_errors"] = None
    except json.JSONDecodeError as e:
        state["error"] = f"QueryPlan repair failed: {e}"

    state["retry_count"] = state.get("retry_count", 0) + 1

    return state
