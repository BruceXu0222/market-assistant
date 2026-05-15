"""Plan generation node powered by LLMQueryPlanner."""

from typing import Dict, Any
from datetime import datetime, timedelta

from core.llm_planner import LLMQueryPlanner, generate_query_plan
def plan_gen_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a QueryPlan and attach it to workflow state."""

    user_message = state.get("user_message", "")
    default_date = state.get("default_date")
    default_market = state.get("default_market", "ALL")
    history = state.get("history", [])

    if not default_date:
        yesterday = datetime.now() - timedelta(days=1)
        default_date = yesterday.strftime("%Y%m%d")

    context = None
    if history:
        recent_history = history[-3:] if len(history) > 3 else history
        context = {"recent_queries": recent_history}

    try:
        planner = LLMQueryPlanner()
        query_plan, validation_errors = planner.generate_plan(
            user_query=user_message,
            default_date=default_date,
            default_market=default_market,
            context=context,
        )

        state["query_plan"] = query_plan
        state["validation_errors"] = validation_errors if validation_errors else None

        if validation_errors:
            print(f"[PlanGen] Validation warnings: {validation_errors}")

    except Exception as e:
        state["error"] = f"Plan generation failed: {str(e)}"
        state["query_plan"] = None
        state["validation_errors"] = [str(e)]
        print(f"[PlanGen] Error: {e}")

    session_id = state.get("session_id", "unknown")
    print(f"[PlanGen] session={session_id}, plan={state.get('query_plan')}")

    return state


def generate_plan_from_query(
    query: str,
    date: str = None,
    market: str = "ALL",
) -> Dict[str, Any]:
    """Generate a QueryPlan for direct tests or utilities."""
    plan, errors = generate_query_plan(query, date, market)
    if errors:
        plan["_validation_errors"] = errors
    return plan


if __name__ == "__main__":
    print("PlanGen Node Test")
    print("=" * 60)

    test_state = {
        "session_id": "test-001",
        "user_message": "Show the top 10 gainers today",
        "default_date": "20250115",
        "default_market": "ALL",
        "history": [],
    }

    print(f"Input: {test_state['user_message']}")
    print("-" * 40)

    result_state = plan_gen_node(test_state)

    print(f"QueryPlan: {result_state.get('query_plan')}")
    print(f"Validation errors: {result_state.get('validation_errors')}")
    print(f"Error: {result_state.get('error')}")
