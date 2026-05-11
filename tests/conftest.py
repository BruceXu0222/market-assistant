"""
Pytest 配置文件
==============

提供共享的 fixtures 和配置
"""

import pytest
from pathlib import Path
import sys

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_query_plan():
    """
    示例 QueryPlan

    TODO: 根据实际需要调整
    """
    return {
        "date": "20250115",
        "market": "HK",
        "metrics": ["涨幅"],
        "filters": [
            {"field": "TotalValueTrade", "op": ">", "value": 1000000}
        ],
        "order_by": [
            {"field": "涨幅", "desc": True}
        ],
        "limit": 10,
        "output_fields": ["SecurityID", "LastPx", "PreClosePx", "涨幅"],
    }


@pytest.fixture
def sample_parquet_paths(tmp_path):
    """
    示例 Parquet 文件路径（用于测试）

    TODO: 创建临时测试文件
    """
    # 创建临时目录
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir()

    # 返回测试文件路径（实际文件需要在测试中创建）
    return [str(test_data_dir / "test.parquet")]


@pytest.fixture
def mock_llm_response():
    """
    模拟 LLM 响应

    TODO: 根据实际需要调整
    """
    return {
        "plan_gen": '{"date": "20250115", "market": "ALL", "metrics": ["涨幅"], "filters": [], "order_by": [{"field": "涨幅", "desc": true}], "limit": 10, "output_fields": ["SecurityID", "LastPx", "PreClosePx", "涨幅"]}',
        "narrate": "根据查询结果，今日涨幅前10的股票整体表现强劲。",
    }
