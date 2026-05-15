import json

import pytest

from core.llm_planner import LLMQueryPlanner
from core.sql_compiler import SQLCompilerEnhanced


class StaticLLM:
    def chat(self, *args, **kwargs):
        return json.dumps({
            "intent": "Rank US decliners",
            "date": "20250115",
            "market": "US",
            "query_type": "basic",
            "select_fields": ["Market", "SecurityID", "Symbol", "ClosePx", "ChangePct"],
            "metrics": [],
            "filters": [],
            "order_by": [{"field": "ChangePct", "desc": False}],
            "limit": 10,
        })


def test_planner_and_compiler_integration():
    planner = LLMQueryPlanner(StaticLLM())
    plan, errors = planner.generate_plan("Show the 10 biggest US stock decliners today", default_date="20250115")

    assert errors == []
    assert plan["market"] == "US"
    assert plan["limit"] == 10

    sql = SQLCompilerEnhanced().compile(plan, ["data/test.parquet"])
    assert "SELECT" in sql
    assert "ORDER BY ChangePct ASC" in sql


def test_aggregation_sql_integration():
    plan = {
        "query_type": "stats",
        "date": "20250115",
        "market": "ALL",
        "select_fields": [],
        "metrics": [],
        "filters": [],
        "order_by": [],
        "aggregations": [
            {"func": "count", "field": "*", "alias": "StockCount"},
            {"func": "sum", "field": "TotalValueTrade", "alias": "TotalTradedValue"},
        ],
        "limit": 1,
    }
    sql = SQLCompilerEnhanced().compile(plan, ["data/test.parquet"])
    assert 'COUNT(*) AS "StockCount"' in sql
    assert 'SUM(TotalValueTrade) AS "TotalTradedValue"' in sql


@pytest.mark.parametrize(
    "query",
    [
        "Which HK stocks had the highest turnover today?",
        "Which stocks have turnover rate above 5% today?",
        "Show Tesla's price trend in January 2025",
    ],
)
def test_common_english_queries_return_valid_plans(query):
    planner = LLMQueryPlanner(StaticLLM())
    plan, errors = planner.generate_plan(query, default_date="20250115", default_market="ALL")
    assert isinstance(plan, dict)
    assert errors == []
