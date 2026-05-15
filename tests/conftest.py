import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_query_plan():
    return {
        "date": "20250115",
        "market": "ALL",
        "metrics": ["GainPct"],
        "filters": [],
        "order_by": [{"field": "GainPct", "desc": True}],
        "limit": 10,
        "output_fields": ["SecurityID", "LastPx", "PreClosePx", "GainPct"],
    }


@pytest.fixture
def sample_parquet_path(tmp_path):
    return tmp_path / "test.parquet"


@pytest.fixture
def mock_llm_response():
    return {
        "plan_gen": '{"date": "20250115", "market": "ALL", "metrics": ["GainPct"], "filters": [], "order_by": [{"field": "GainPct", "desc": true}], "limit": 10, "output_fields": ["SecurityID", "LastPx", "PreClosePx", "GainPct"]}',
        "narrate": "The top gainers were broadly strong today.",
    }
