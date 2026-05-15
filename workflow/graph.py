"""LangGraph workflow definition."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph


class GraphState(TypedDict):
    """Shared workflow state."""

    session_id: str
    user_message: str
    default_date: Optional[str]
    default_market: str
    history: Annotated[List[Dict[str, str]], operator.add]
    query_type: Optional[str]
    query_plan: Optional[Dict[str, Any]]
    validation_errors: Optional[List[str]]
    retry_count: int
    sql: Optional[str]
    dataframe: Optional[Any]
    summary: Optional[Dict[str, Any]]
    table: Optional[List[Dict[str, Any]]]
    commentary: str
    error: Optional[str]
    debug: Optional[Dict[str, Any]]


def router_node(state: GraphState) -> GraphState:
    """Route the message into the market-query path."""
    print(f"\n{'=' * 80}")
    print("[1/8 Router] Starting route decision")
    print(f"[1/8 Router] User input: {state.get('user_message', '')[:80]}...")
    state["query_type"] = "market_query"
    print(f"[1/8 Router] Done: query_type = {state['query_type']}")
    return state


def plan_gen_node(state: GraphState) -> GraphState:
    """Create a simple QueryPlan for the workflow demo path."""
    print(f"\n{'=' * 80}")
    print("[2/8 PlanGen] Creating QueryPlan")

    user_message = state.get("user_message", "").lower()
    print(f"[2/8 PlanGen] Analyzing question: {user_message[:80]}...")

    if "turnover" in user_message or "volume" in user_message:
        state["query_plan"] = {
            "query_type": "basic",
            "date": state.get("default_date", "20250115"),
            "market": state.get("default_market", "ALL"),
            "metrics": [],
            "filters": [],
            "order_by": [{"field": "TotalValueTrade", "desc": True}],
            "limit": 10,
            "output_fields": ["SecurityID", "Symbol", "ClosePx", "TotalValueTrade", "TotalVolumeTrade"],
        }
    elif "amplitude" in user_message:
        state["query_plan"] = {
            "query_type": "basic",
            "date": state.get("default_date", "20250115"),
            "market": state.get("default_market", "ALL"),
            "metrics": [],
            "filters": [],
            "order_by": [{"field": "Amplitude", "desc": True}],
            "limit": 10,
            "output_fields": ["SecurityID", "Symbol", "ClosePx", "HighPx", "LowPx", "Amplitude"],
        }
    else:
        state["query_plan"] = {
            "query_type": "basic",
            "date": state.get("default_date", "20250115"),
            "market": state.get("default_market", "ALL"),
            "metrics": [],
            "filters": [],
            "order_by": [{"field": "ChangePct", "desc": True}],
            "limit": 10,
            "output_fields": ["SecurityID", "Symbol", "ClosePx", "PreClosePx", "ChangePct"],
        }

    print("[2/8 PlanGen] QueryPlan created")
    return state


def validate_node(state: GraphState) -> GraphState:
    """Validate the QueryPlan placeholder path."""
    print(f"\n{'=' * 80}")
    print("[3/8 Validate] Validating QueryPlan")
    state["validation_errors"] = None
    print("[3/8 Validate] Validation passed")
    return state


def repair_node(state: GraphState) -> GraphState:
    """Increment retry count for the repair path."""
    print(f"\n{'=' * 80}")
    print("[4/8 Repair] Repairing QueryPlan")
    print(f"[4/8 Repair] Retry count: {state.get('retry_count', 0)}/2")
    state["retry_count"] = state.get("retry_count", 0) + 1
    print("[4/8 Repair] Repair complete")
    return state


def execute_node(state: GraphState) -> GraphState:
    """Compile and execute the QueryPlan."""
    print(f"\n{'=' * 80}")
    print("[5/8 Execute] Executing SQL query")

    try:
        import duckdb

        from core.path_resolver import resolve_parquet_paths
        from core.sql_compiler import SQLCompilerEnhanced

        parquet_paths = resolve_parquet_paths(
            state["query_plan"].get("date"),
            state["query_plan"].get("market", "ALL"),
        )

        compiler = SQLCompilerEnhanced()
        sql = compiler.compile(state["query_plan"], parquet_paths)
        state["sql"] = sql

        conn = duckdb.connect(":memory:")
        result = conn.execute(sql).fetchdf()
        conn.close()
        state["dataframe"] = result

        print("[5/8 Execute] Query complete")
        print(f"[5/8 Execute] SQL length: {len(state['sql'])} characters")
        print(f"[5/8 Execute] Rows returned: {len(result)}")

    except Exception as exc:
        print(f"[5/8 Execute] Query failed: {exc}")
        state["error"] = str(exc)
        state["dataframe"] = None

    return state


def postprocess_node(state: GraphState) -> GraphState:
    """Format a DataFrame into table and summary outputs."""
    print(f"\n{'=' * 80}")
    print("[6/8 PostProcess] Post-processing result")

    try:
        df = state.get("dataframe")
        if df is not None and not df.empty:
            state["table"] = df.to_dict(orient="records")
            state["summary"] = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
            }
            print("[6/8 PostProcess] Post-processing complete")
        else:
            state["table"] = []
            state["summary"] = {"row_count": 0}
            print("[6/8 PostProcess] Result is empty")
    except Exception as exc:
        print(f"[6/8 PostProcess] Post-processing failed: {exc}")
        state["table"] = []
        state["summary"] = {"row_count": 0, "error": str(exc)}

    return state


def narrate_node(state: GraphState) -> GraphState:
    """Create fallback commentary."""
    print(f"\n{'=' * 80}")
    print("[7/8 Narrate] Creating commentary")
    row_count = state.get("summary", {}).get("row_count", 0)
    state["commentary"] = f"Query complete. Returned {row_count} rows."
    print("[7/8 Narrate] Commentary ready")
    return state


def memory_update_node(state: GraphState) -> GraphState:
    """Finalize workflow state."""
    print(f"\n{'=' * 80}")
    print("[8/8 MemoryUpdate] Updating session state")
    print(f"[8/8 MemoryUpdate] History count: {len(state.get('history', []))}")
    print(f"{'=' * 80}\n")
    return state


def should_repair(state: GraphState) -> str:
    """Return the next edge after validation."""
    if state.get("validation_errors"):
        if state.get("retry_count", 0) < 2:
            print("[Condition] Validation failed; routing to repair")
            return "repair"
        print("[Condition] Retry limit reached; ending")
        return "error"

    print("[Condition] Validation passed; routing to execute")
    return "execute"


def route_by_query_type(state: GraphState) -> str:
    """Return the first workflow branch."""
    query_type = state.get("query_type", "market_query")
    if query_type == "chitchat":
        print("[Condition] Chitchat query; ending")
        return "chitchat"
    if query_type == "field_explain":
        print("[Condition] Field explanation query; ending")
        return "field_explain"
    print("[Condition] Market query; routing to plan generation")
    return "plan_gen"


def build_graph() -> StateGraph:
    """Build and compile the LangGraph state machine."""
    print("\n[Graph] Building LangGraph workflow...")
    workflow = StateGraph(GraphState)

    workflow.add_node("router", router_node)
    workflow.add_node("plan_gen", plan_gen_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("repair", repair_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("postprocess", postprocess_node)
    workflow.add_node("narrate", narrate_node)
    workflow.add_node("memory_update", memory_update_node)

    workflow.set_entry_point("router")
    workflow.add_conditional_edges(
        "router",
        route_by_query_type,
        {"plan_gen": "plan_gen", "chitchat": END, "field_explain": END},
    )
    workflow.add_edge("plan_gen", "validate")
    workflow.add_conditional_edges(
        "validate",
        should_repair,
        {"execute": "execute", "repair": "repair", "error": END},
    )
    workflow.add_edge("repair", "validate")
    workflow.add_edge("execute", "postprocess")
    workflow.add_edge("postprocess", "narrate")
    workflow.add_edge("narrate", "memory_update")
    workflow.add_edge("memory_update", END)

    print("[Graph] LangGraph workflow ready\n")
    return workflow.compile()


graph = build_graph()


if __name__ == "__main__":
    initial_state: GraphState = {
        "session_id": "test-session",
        "user_message": "Show the top 10 gainers today",
        "default_date": "20250115",
        "default_market": "ALL",
        "history": [],
        "query_type": None,
        "query_plan": None,
        "validation_errors": None,
        "retry_count": 0,
        "sql": None,
        "dataframe": None,
        "summary": None,
        "table": None,
        "commentary": "",
        "error": None,
        "debug": {},
    }
    result = graph.invoke(initial_state)
    print(f"Final query_type: {result.get('query_type')}")
    print(f"Rows: {len(result.get('table', []))}")
