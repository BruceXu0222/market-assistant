"""
QueryPlan 校验单元测试
======================

测试内容：
1. 日期格式校验
2. 市场代码校验
3. Limit 范围校验
4. 字段白名单校验
5. 操作符白名单校验

注意：验证逻辑已移至 llm_planner.py 中的 LLMQueryPlanner._validate_plan()
"""

import pytest
from core.llm_planner import (
    LLMQueryPlanner,
    ALL_ALLOWED_FIELDS,
    DERIVED_METRICS,
    ALLOWED_OPERATORS,
)


# ============================================================================
# 测试用例
# ============================================================================

class TestPlanValidation:
    """QueryPlan 校验测试类"""

    def setup_method(self):
        """每个测试方法前执行：初始化 Planner"""
        self.planner = LLMQueryPlanner(llm_client=None)  # 不需要 LLM 客户端做验证

    def test_valid_plan(self):
        """测试有效的 QueryPlan"""
        plan = {
            "date": "20250115",
            "market": "XSHG",
            "metrics": ["涨幅"],
            "filters": [
                {"field": "TotalValueTrade", "op": ">", "value": 1000000}
            ],
            "order_by": [
                {"field": "涨幅", "desc": True}
            ],
            "limit": 10,
            "select_fields": ["SecurityID", "ClosePx", "PreClosePx"],
        }

        errors = self.planner._validate_plan(plan)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_invalid_date_format(self):
        """测试无效的日期格式"""
        plan = {
            "date": "2025-01-15",  # 错误格式（应为 YYYYMMDD）
            "market": "XSHG",
            "limit": 10,
            "select_fields": ["SecurityID"],
        }

        errors = self.planner._validate_plan(plan)
        assert len(errors) > 0, "Expected validation error for invalid date"
        assert any("日期格式" in e for e in errors)

    def test_invalid_market(self):
        """测试无效的市场代码"""
        plan = {
            "date": "20250115",
            "market": "INVALID",  # 错误市场
            "limit": 10,
            "select_fields": ["SecurityID"],
        }

        errors = self.planner._validate_plan(plan)
        assert len(errors) > 0, "Expected validation error for invalid market"
        assert any("市场代码" in e for e in errors)

    def test_invalid_limit_too_small(self):
        """测试 Limit 太小"""
        plan = {
            "date": "20250115",
            "market": "XSHG",
            "limit": 0,  # 太小
            "select_fields": ["SecurityID"],
        }

        errors = self.planner._validate_plan(plan)
        assert len(errors) > 0, "Expected validation error for limit=0"
        assert any("limit" in e.lower() for e in errors)

    def test_invalid_limit_too_large(self):
        """测试 Limit 太大"""
        plan = {
            "date": "20250115",
            "market": "XSHG",
            "limit": 100001,  # 太大（>10000）
            "select_fields": ["SecurityID"],
        }

        errors = self.planner._validate_plan(plan)
        assert len(errors) > 0, "Expected validation error for limit=100001"
        assert any("limit" in e.lower() for e in errors)

    def test_invalid_operator(self):
        """测试无效的操作符"""
        plan = {
            "date": "20250115",
            "market": "XSHG",
            "limit": 10,
            "select_fields": ["SecurityID"],
            "filters": [
                {"field": "ClosePx", "op": ">>", "value": 100}  # 无效操作符
            ],
        }

        errors = self.planner._validate_plan(plan)
        assert len(errors) > 0, "Expected validation error for invalid operator"
        assert any("操作符" in e for e in errors)

    def test_invalid_field_in_select(self):
        """测试 select_fields 中的无效字段"""
        plan = {
            "date": "20250115",
            "market": "XSHG",
            "limit": 10,
            "select_fields": ["SecurityID", "InvalidField"],  # 无效字段
        }

        errors = self.planner._validate_plan(plan)
        assert len(errors) > 0, "Expected validation error for invalid field"
        assert any("白名单" in e for e in errors)

    def test_invalid_metric(self):
        """测试无效的衍生指标"""
        plan = {
            "date": "20250115",
            "market": "XSHG",
            "limit": 10,
            "select_fields": ["SecurityID"],
            "metrics": ["涨幅", "不存在的指标"],  # 无效指标
        }

        errors = self.planner._validate_plan(plan)
        assert len(errors) > 0, "Expected validation error for invalid metric"
        assert any("白名单" in e for e in errors)

    def test_valid_markets(self):
        """测试所有有效的市场代码"""
        valid_markets = ["XSHG", "XSHE", "US", "ALL"]

        for market in valid_markets:
            plan = {
                "date": "20250115",
                "market": market,
                "limit": 10,
                "select_fields": ["SecurityID"],
            }
            errors = self.planner._validate_plan(plan)
            assert errors == [], f"Market {market} should be valid, got errors: {errors}"

    def test_valid_operators(self):
        """测试所有有效的操作符"""
        valid_ops = [">", "<", "=", ">=", "<=", "!="]

        for op in valid_ops:
            plan = {
                "date": "20250115",
                "market": "ALL",
                "limit": 10,
                "select_fields": ["SecurityID"],
                "filters": [{"field": "ClosePx", "op": op, "value": 100}],
            }
            errors = self.planner._validate_plan(plan)
            assert errors == [], f"Operator {op} should be valid, got errors: {errors}"


class TestFieldWhitelist:
    """字段白名单测试"""

    def test_base_fields_in_whitelist(self):
        """测试基础字段在白名单中"""
        required_fields = [
            "SecurityID", "ClosePx", "PreClosePx", "HighPx", "LowPx",
            "TotalValueTrade", "TotalVolumeTrade", "MaxPx", "MinPx"
        ]

        for field in required_fields:
            assert field in ALL_ALLOWED_FIELDS, f"Field {field} should be in whitelist"

    def test_derived_metrics_in_whitelist(self):
        """测试衍生指标在白名单中"""
        required_metrics = ["涨幅", "跌幅", "振幅", "是否涨停", "是否跌停"]

        for metric in required_metrics:
            assert metric in DERIVED_METRICS, f"Metric {metric} should be in DERIVED_METRICS"
            assert metric in ALL_ALLOWED_FIELDS, f"Metric {metric} should be in ALL_ALLOWED_FIELDS"


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
