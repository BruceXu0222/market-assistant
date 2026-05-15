import json

from core.llm_planner import (
    ALLOWED_OPERATORS,
    ALL_ALLOWED_FIELDS,
    BASE_FIELDS,
    DERIVED_METRICS,
    LLMQueryPlanner,
    generate_query_plan,
)
from core.sql_compiler import SQLCompilerEnhanced


class MockLLMClient:
    def __init__(self, payload=None):
        self.payload = payload or {
            "intent": "Rank top gainers",
            "date": "20250115",
            "market": "ALL",
            "select_fields": ["SecurityID", "ClosePx", "PreClosePx"],
            "metrics": ["GainPct"],
            "filters": [],
            "order_by": [{"field": "GainPct", "desc": True}],
            "limit": 10,
        }
        self.call_count = 0

    def chat(self, *args, **kwargs):
        self.call_count += 1
        return json.dumps(self.payload)


def test_base_fields_exist():
    for field in ["SecurityID", "Symbol", "ClosePx", "PreClosePx", "TotalValueTrade", "ChangePct", "Amplitude", "TurnoverRate"]:
        assert field in BASE_FIELDS


def test_derived_metrics_exist():
    assert DERIVED_METRICS == {"GainPct": "ChangePct", "LossPct": "-ChangePct"}
    assert "GainPct" in ALL_ALLOWED_FIELDS


def test_allowed_operators():
    for op in [">", "<", "=", ">=", "<="]:
        assert op in ALLOWED_OPERATORS


def test_generate_plan_basic():
    planner = LLMQueryPlanner(MockLLMClient())
    plan, errors = planner.generate_plan("Show the top 10 gainers", default_date="20250115", default_market="ALL")

    assert errors == []
    assert plan["date"] == "20250115"
    assert plan["market"] == "ALL"
    assert plan["limit"] == 10
    assert plan["order_by"] == [{"field": "ChangePct", "desc": True}]


def test_generate_plan_filter():
    payload = {
        "intent": "Filter by traded value",
        "date": "20250115",
        "market": "ALL",
        "select_fields": ["SecurityID", "TotalValueTrade"],
        "filters": [{"field": "TotalValueTrade", "op": ">", "value": 10000000000}],
        "limit": 100,
    }
    planner = LLMQueryPlanner(MockLLMClient(payload))
    plan, errors = planner.generate_plan("Show stocks with traded value above 10 billion", default_date="20250115")

    assert errors == []
    assert plan["filters"][0]["field"] == "TotalValueTrade"


def test_default_date_applied():
    payload = {"intent": "Query", "market": "ALL", "select_fields": ["SecurityID"], "limit": 10}
    planner = LLMQueryPlanner(MockLLMClient(payload))
    plan, _ = planner.generate_plan("Show top gainers", default_date="20250120")
    assert plan["date"] == "20250120"


def test_default_market_applied():
    payload = {"intent": "Query", "date": "20250115", "select_fields": ["SecurityID"], "limit": 10}
    planner = LLMQueryPlanner(MockLLMClient(payload))
    plan, _ = planner.generate_plan("Show top gainers", default_market="HK")
    assert plan["market"] == "HK"


def test_validation_rejects_invalid_field():
    payload = {
        "intent": "Bad field",
        "date": "20250115",
        "market": "ALL",
        "select_fields": ["SecurityID", "BadField"],
        "limit": 10,
    }
    planner = LLMQueryPlanner(MockLLMClient(payload))
    _, errors = planner.generate_plan("bad field")
    assert any("allowed" in error for error in errors)


def test_validation_rejects_invalid_date():
    payload = {"intent": "Bad date", "date": "2025-01-15", "market": "ALL", "select_fields": ["SecurityID"], "limit": 10}
    planner = LLMQueryPlanner(MockLLMClient(payload))
    _, errors = planner.generate_plan("bad date")
    assert any("date format" in error for error in errors)


def test_parse_markdown_json():
    class MarkdownMock:
        def chat(self, *args, **kwargs):
            return "```json\n{\"date\": \"20250115\", \"market\": \"ALL\", \"select_fields\": [\"SecurityID\"], \"limit\": 10}\n```"

    planner = LLMQueryPlanner(MarkdownMock())
    plan, errors = planner.generate_plan("Show data")
    assert errors == []
    assert plan["date"] == "20250115"


def test_generated_plan_compiles_to_sql():
    planner = LLMQueryPlanner(MockLLMClient())
    plan, errors = planner.generate_plan("Show the top 10 gainers", default_date="20250115")
    assert errors == []

    sql = SQLCompilerEnhanced().compile(plan, ["data/test.parquet"])
    assert "SELECT" in sql
    assert "ORDER BY" in sql


def test_generate_query_plan_helper():
    plan, errors = generate_query_plan("Show top gainers", "20250115", "ALL", MockLLMClient())
    assert errors == []
    assert plan["date"] == "20250115"
