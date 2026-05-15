from core.llm_planner import ALL_ALLOWED_FIELDS, ALLOWED_OPERATORS, DERIVED_METRICS, LLMQueryPlanner


def planner():
    return LLMQueryPlanner(llm_client=None)


def test_valid_plan_passes():
    plan = {
        "date": "20250115",
        "market": "HK",
        "metrics": ["GainPct"],
        "filters": [{"field": "TotalValueTrade", "op": ">", "value": 1000000}],
        "order_by": [{"field": "GainPct", "desc": True}],
        "limit": 10,
        "select_fields": ["SecurityID", "ClosePx"],
    }
    assert planner()._validate_plan(plan) == []


def test_invalid_date_format():
    errors = planner()._validate_plan({"date": "2025-01-15", "market": "HK", "limit": 10, "select_fields": ["SecurityID"]})
    assert any("date format" in error for error in errors)


def test_invalid_market():
    errors = planner()._validate_plan({"date": "20250115", "market": "INVALID", "limit": 10, "select_fields": ["SecurityID"]})
    assert any("market code" in error for error in errors)


def test_invalid_limit_bounds():
    assert planner()._validate_plan({"date": "20250115", "market": "HK", "limit": 0, "select_fields": ["SecurityID"]})
    assert planner()._validate_plan({"date": "20250115", "market": "HK", "limit": 100001, "select_fields": ["SecurityID"]})


def test_invalid_operator():
    errors = planner()._validate_plan({
        "date": "20250115",
        "market": "HK",
        "limit": 10,
        "select_fields": ["SecurityID"],
        "filters": [{"field": "ClosePx", "op": ">>", "value": 100}],
    })
    assert any("Operator" in error for error in errors)


def test_invalid_field_and_metric():
    field_errors = planner()._validate_plan({"date": "20250115", "market": "HK", "limit": 10, "select_fields": ["BadField"]})
    metric_errors = planner()._validate_plan({"date": "20250115", "market": "HK", "limit": 10, "select_fields": ["SecurityID"], "metrics": ["BadMetric"]})
    assert any("allowed" in error for error in field_errors)
    assert any("allowed" in error for error in metric_errors)


def test_valid_markets_and_operators():
    for market in ["HK", "US", "ALL"]:
        assert planner()._validate_plan({"date": "20250115", "market": market, "limit": 10, "select_fields": ["SecurityID"]}) == []
    for op in [">", "<", "=", ">=", "<=", "!="]:
        assert op in ALLOWED_OPERATORS


def test_field_allowlist():
    for field in ["SecurityID", "ClosePx", "PreClosePx", "TotalValueTrade", "TotalVolumeTrade", "ChangePct", "Amplitude", "TurnoverRate"]:
        assert field in ALL_ALLOWED_FIELDS
    assert "GainPct" in DERIVED_METRICS
    assert "LossPct" in DERIVED_METRICS
