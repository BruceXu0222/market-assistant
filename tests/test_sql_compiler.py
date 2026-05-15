from core.sql_compiler import METRIC_DEFINITIONS, SQLCompilerEnhanced, VALID_BASE_FIELDS


def compiler():
    return SQLCompilerEnhanced()


def test_basic_query_compile():
    plan = {
        "query_type": "basic",
        "date": "20250115",
        "market": "ALL",
        "metrics": [],
        "filters": [],
        "order_by": [],
        "limit": 10,
        "select_fields": ["SecurityID", "ClosePx"],
    }
    sql = compiler().compile(plan, ["data/test.parquet"])
    assert "SELECT" in sql
    assert "SecurityID" in sql
    assert "ClosePx" in sql
    assert "LIMIT 10" in sql


def test_where_clause_compile():
    plan = {
        "query_type": "filter",
        "date": "20250115",
        "market": "ALL",
        "metrics": [],
        "filters": [{"field": "TotalValueTrade", "op": ">", "value": 1000000}],
        "order_by": [],
        "limit": 100,
        "select_fields": ["SecurityID", "TotalValueTrade"],
    }
    sql = compiler().compile(plan, ["data/test.parquet"])
    assert "WHERE" in sql
    assert "TotalValueTrade > 1000000" in sql


def test_derived_metric_order_by():
    plan = {
        "query_type": "basic",
        "date": "20250115",
        "market": "ALL",
        "metrics": ["GainPct"],
        "filters": [],
        "order_by": [{"field": "GainPct", "desc": True}],
        "limit": 10,
        "select_fields": ["SecurityID", "GainPct"],
    }
    sql = compiler().compile(plan, ["data/test.parquet"])
    assert 'AS "GainPct"' in sql
    assert 'ORDER BY "GainPct" DESC' in sql


def test_aggregation_query_compile():
    plan = {
        "query_type": "stats",
        "date": "20250115",
        "market": "ALL",
        "metrics": [],
        "filters": [],
        "order_by": [],
        "limit": 1,
        "select_fields": [],
        "aggregations": [
            {"func": "sum", "field": "TotalValueTrade", "alias": "TotalTradedValue"},
            {"func": "count", "field": "*", "alias": "StockCount"},
        ],
        "group_by": [],
    }
    sql = compiler().compile(plan, ["data/test.parquet"])
    assert 'SUM(TotalValueTrade) AS "TotalTradedValue"' in sql
    assert 'COUNT(*) AS "StockCount"' in sql


def test_group_by_metric_compile():
    plan = {
        "query_type": "stats",
        "date": "20250115",
        "market": "ALL",
        "metrics": ["PriceBucket"],
        "filters": [],
        "order_by": [{"field": "AverageGainPct", "desc": True}],
        "limit": 10,
        "select_fields": ["PriceBucket"],
        "aggregations": [
            {"func": "count", "field": "*", "alias": "StockCount"},
            {"func": "avg", "field": "GainPct", "alias": "AverageGainPct"},
        ],
        "group_by": ["PriceBucket"],
    }
    sql = compiler().compile(plan, ["data/test.parquet"])
    assert "GROUP BY PriceBucket" in sql
    assert 'AS "PriceBucket"' in sql
    assert 'AS "AverageGainPct"' in sql


def test_union_for_multiple_files():
    plan = {
        "query_type": "basic",
        "date": "20250115",
        "market": "ALL",
        "metrics": [],
        "filters": [],
        "order_by": [],
        "limit": 10,
        "select_fields": ["SecurityID"],
    }
    sql = compiler().compile(plan, ["data/file1.parquet", "data/file2.parquet"])
    assert "parquet_scan" in sql


def test_snapshot_dedup_for_legacy_source():
    sql = compiler()._build_from_clause(["data/test.parquet"], use_latest_snapshot=True)
    assert "ROW_NUMBER()" in sql
    assert "PARTITION BY SecurityID" in sql


def test_field_definitions():
    assert "GainPct" in METRIC_DEFINITIONS
    assert "SecurityID" in VALID_BASE_FIELDS
