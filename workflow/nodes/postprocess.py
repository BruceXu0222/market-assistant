"""Post-processing node for query results."""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from core.stock_names import english_stock_name


def postprocess_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a DataFrame into table rows and a compact summary."""
    dataframe = state.get("dataframe")

    if dataframe is None or (isinstance(dataframe, pd.DataFrame) and dataframe.empty):
        state["table"] = []
        state["summary"] = {"row_count": 0}
        return state

    df_formatted = dataframe.copy()
    if "SecurityID" in df_formatted.columns and "Symbol" in df_formatted.columns:
        df_formatted["Symbol"] = df_formatted.apply(
            lambda row: english_stock_name(row.get("SecurityID"), row.get("Symbol")),
            axis=1,
        )

    numeric_cols = df_formatted.select_dtypes(include=["float64", "float32"]).columns
    df_formatted[numeric_cols] = df_formatted[numeric_cols].round(4)
    df_formatted = df_formatted.where(pd.notna(df_formatted), None)

    state["table"] = df_formatted.to_dict(orient="records")

    summary = {
        "row_count": len(dataframe),
        "column_count": len(dataframe.columns),
        "columns": list(dataframe.columns),
    }
    query_plan = state.get("query_plan", {})

    for metric in query_plan.get("metrics", []):
        if metric in dataframe.columns and pd.api.types.is_numeric_dtype(dataframe[metric]):
            col = dataframe[metric]
            summary[f"{metric}_max"] = round(col.max(), 4)
            summary[f"{metric}_min"] = round(col.min(), 4)
            summary[f"{metric}_mean"] = round(col.mean(), 4)

    state["summary"] = summary
    return state
