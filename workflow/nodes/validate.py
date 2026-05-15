"""Validation node for QueryPlans."""

from typing import Dict, Any, List


def validate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Check whether the workflow has an executable QueryPlan."""

    query_plan = state.get("query_plan")
    validation_errors = state.get("validation_errors")

    if not query_plan:
        if not validation_errors:
            state["validation_errors"] = ["QueryPlan is empty"]
        return state

    if "error" in query_plan:
        if not validation_errors:
            state["validation_errors"] = [query_plan["error"]]
        return state

    errors = validation_errors or []

    if not query_plan.get("date"):
        errors.append("Missing date field")

    if not query_plan.get("market"):
        errors.append("Missing market field")

    if not query_plan.get("select_fields") and not query_plan.get("aggregations"):
        query_plan["select_fields"] = ["SecurityID", "ClosePx", "PreClosePx"]

    state["validation_errors"] = errors if errors else None

    session_id = state.get("session_id", "unknown")
    if errors:
        print(f"[Validate] session={session_id}, errors={errors}")
    else:
        print(f"[Validate] session={session_id}, validation passed")

    return state


def should_repair(state: Dict[str, Any]) -> str:
    """Return the next edge after validation."""

    validation_errors = state.get("validation_errors")
    retry_count = state.get("retry_count", 0)

    if not validation_errors:
        return "execute"

    if retry_count >= 2:
        print(f"[Validate] Retry limit reached ({retry_count})")
        return "end"

    return "repair"
