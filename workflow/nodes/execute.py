"""Execution node for QueryPlan SQL."""

from __future__ import annotations

import time
from typing import Any, Dict

from core.duckdb_engine import DuckDBEngine
from core.path_resolver import resolve_parquet_paths
from core.sql_compiler import SQLCompilerEnhanced


def execute_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Compile the current QueryPlan and execute it with DuckDB."""
    query_plan = state.get("query_plan")
    if not query_plan:
        state["error"] = "QueryPlan is empty and cannot be executed"
        return state

    start_time = time.time()

    try:
        date = query_plan.get("date")
        market = query_plan.get("market", "ALL")
        paths = resolve_parquet_paths(date, market)
    except Exception as exc:
        state["error"] = f"Data files were not found: date={query_plan.get('date')}, market={query_plan.get('market')}: {exc}"
        return state

    try:
        compiler = SQLCompilerEnhanced()
        state["sql"] = compiler.compile(query_plan, paths)
    except Exception as exc:
        state["error"] = f"SQL compilation failed: {exc}"
        return state

    with DuckDBEngine() as engine:
        try:
            state["dataframe"] = engine.execute(state["sql"])
        except Exception as exc:
            state["error"] = f"DuckDB query failed: {exc}"
            return state

    elapsed_ms = (time.time() - start_time) * 1000
    state.setdefault("debug", {}).setdefault("latency_ms", {})["execute"] = elapsed_ms
    return state
