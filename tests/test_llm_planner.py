"""
LLM 查询计划生成器单元测试
==========================

测试内容：
1. LLMQueryPlanner 计划生成
2. JSON 解析
3. 字段白名单验证
4. 默认值应用
5. 与 SQL 编译器集成
"""

import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from core.llm_planner import (
    LLMQueryPlanner,
    generate_query_plan,
    BASE_FIELDS,
    DERIVED_METRICS,
    ALL_ALLOWED_FIELDS,
    ALLOWED_OPERATORS,
)
from core.sql_compiler import SQLCompilerEnhanced


# ============================================================================
# 模拟 LLM 客户端
# ============================================================================

class MockLLMClient:
    """模拟 LLM 客户端，用于在没有实际 LLM 服务的情况下进行测试"""

    def __init__(self, response_map=None):
        self.response_map = response_map or {}
        self.call_count = 0

    def chat(self, prompt, system_prompt=None, temperature=0.1, max_tokens=1024):
        self.call_count += 1

        # 根据特定查询模式返回相应的响应
        if "涨幅前10" in prompt or "涨幅最高" in prompt:
            return json.dumps({
                "intent": "查询涨幅最高的前10只股票",
                "date": "20250115",
                "market": "ALL",
                "select_fields": ["SecurityID", "ClosePx", "PreClosePx"],
                "metrics": ["涨幅"],
                "filters": [],
                "order_by": [{"field": "涨幅", "desc": True}],
                "limit": 10
            }, ensure_ascii=False)

        if "成交额超过" in prompt or "成交额大于" in prompt:
            return json.dumps({
                "intent": "筛选成交额超过指定金额的股票",
                "date": "20250115",
                "market": "ALL",
                "select_fields": ["SecurityID", "ClosePx", "TotalValueTrade"],
                "metrics": [],
                "filters": [{"field": "TotalValueTrade", "op": ">", "value": 10000000000}],
                "order_by": [{"field": "TotalValueTrade", "desc": True}],
                "limit": 100
            }, ensure_ascii=False)

        if "涨停" in prompt:
            return json.dumps({
                "intent": "查询涨停股票",
                "date": "20250115",
                "market": "ALL",
                "select_fields": ["SecurityID", "ClosePx", "PreClosePx", "MaxPx"],
                "metrics": ["涨幅", "是否涨停"],
                "filters": [{"field": "是否涨停", "op": "=", "value": 1}],
                "order_by": [{"field": "TotalValueTrade", "desc": True}],
                "limit": 100
            }, ensure_ascii=False)

        if "统计" in prompt and "数量" in prompt:
            return json.dumps({
                "intent": "统计涨跌股票数量",
                "date": "20250115",
                "market": "ALL",
                "select_fields": [],
                "metrics": [],
                "aggregations": [
                    {"func": "COUNT", "field": "CASE WHEN ClosePx > PreClosePx THEN 1 END", "alias": "上涨数量"},
                    {"func": "COUNT", "field": "*", "alias": "总数量"}
                ],
                "limit": 1
            }, ensure_ascii=False)

        # 默认响应
        return json.dumps({
            "intent": "默认查询",
            "date": "20250115",
            "market": "ALL",
            "select_fields": ["SecurityID", "ClosePx"],
            "metrics": [],
            "filters": [],
            "order_by": [],
            "limit": 100
        }, ensure_ascii=False)


# ============================================================================
# 测试 Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_client():
    """创建模拟 LLM 客户端"""
    return MockLLMClient()


@pytest.fixture
def planner(mock_llm_client):
    """创建带有模拟 LLM 客户端的计划生成器"""
    return LLMQueryPlanner(llm_client=mock_llm_client)


@pytest.fixture
def sql_compiler():
    """创建 SQL 编译器用于集成测试"""
    return SQLCompilerEnhanced()


# ============================================================================
# 测试：字段定义
# ============================================================================

class TestFieldDefinitions:
    """测试字段和指标定义"""

    def test_base_fields_exist(self):
        """测试基础字段是否已定义"""
        assert "SecurityID" in BASE_FIELDS
        assert "ClosePx" in BASE_FIELDS
        assert "PreClosePx" in BASE_FIELDS
        assert "TotalValueTrade" in BASE_FIELDS
        # 新增字段（来自 schema）
        assert "Symbol" in BASE_FIELDS
        assert "LastPx" in BASE_FIELDS
        assert "NumTrades" in BASE_FIELDS
        assert "TotalBidQty" in BASE_FIELDS
        assert "TotalOfferQty" in BASE_FIELDS

    def test_derived_metrics_exist(self):
        """测试衍生指标是否已定义"""
        assert "涨幅" in DERIVED_METRICS
        assert "振幅" in DERIVED_METRICS
        assert "是否涨停" in DERIVED_METRICS
        assert "是否跌停" in DERIVED_METRICS
        assert "买卖盘比" in DERIVED_METRICS

    def test_all_allowed_fields_combined(self):
        """测试 ALL_ALLOWED_FIELDS 包含基础字段和衍生指标"""
        assert "SecurityID" in ALL_ALLOWED_FIELDS
        assert "涨幅" in ALL_ALLOWED_FIELDS
        assert len(ALL_ALLOWED_FIELDS) == len(BASE_FIELDS) + len(DERIVED_METRICS)

    def test_allowed_operators(self):
        """测试允许的操作符"""
        assert ">" in ALLOWED_OPERATORS
        assert "<" in ALLOWED_OPERATORS
        assert "=" in ALLOWED_OPERATORS
        assert ">=" in ALLOWED_OPERATORS
        assert "<=" in ALLOWED_OPERATORS


# ============================================================================
# 测试：LLMQueryPlanner
# ============================================================================

class TestLLMQueryPlanner:
    """测试 LLMQueryPlanner 类"""

    def test_generate_plan_basic(self, planner):
        """测试基本计划生成"""
        plan, errors = planner.generate_plan(
            user_query="今天涨幅前10的股票",
            default_date="20250115",
            default_market="ALL"
        )

        assert plan is not None
        assert plan.get("intent") is not None
        assert plan.get("date") == "20250115"
        assert plan.get("market") == "ALL"
        assert errors == []  # 无验证错误

    def test_generate_plan_with_filter(self):
        """测试带过滤条件的计划生成"""
        # 使用返回过滤条件的特定模拟
        class FilterMockLLM:
            def chat(self, *args, **kwargs):
                return json.dumps({
                    "intent": "筛选成交额超过10亿的股票",
                    "date": "20250115",
                    "market": "ALL",
                    "select_fields": ["SecurityID", "TotalValueTrade"],
                    "filters": [{"field": "TotalValueTrade", "op": ">", "value": 10000000000}],
                    "limit": 100
                })

        planner = LLMQueryPlanner(llm_client=FilterMockLLM())
        plan, errors = planner.generate_plan(
            user_query="成交额超过10亿的股票",
            default_date="20250115"
        )

        assert plan is not None
        assert len(plan.get("filters", [])) > 0
        assert errors == []

    def test_generate_plan_limit_stop(self):
        """测试涨停股查询的计划生成"""
        # 使用返回涨停指标的特定模拟
        class ZhangTingMockLLM:
            def chat(self, *args, **kwargs):
                return json.dumps({
                    "intent": "查询涨停股票",
                    "date": "20250115",
                    "market": "ALL",
                    "select_fields": ["SecurityID", "ClosePx"],
                    "metrics": ["是否涨停", "涨幅"],
                    "filters": [{"field": "是否涨停", "op": "=", "value": 1}],
                    "limit": 100
                })

        planner = LLMQueryPlanner(llm_client=ZhangTingMockLLM())
        plan, errors = planner.generate_plan(
            user_query="今天涨停的股票有哪些",
            default_date="20250115"
        )

        assert plan is not None
        assert "是否涨停" in plan.get("metrics", [])
        assert errors == []

    def test_default_date_applied(self):
        """测试默认日期是否被正确应用"""
        # 模拟返回空日期，默认值应被应用
        class NoDateMockLLM:
            def chat(self, *args, **kwargs):
                return json.dumps({
                    "intent": "查询",
                    "market": "ALL",
                    "select_fields": ["SecurityID"],
                    "limit": 10
                })

        planner = LLMQueryPlanner(llm_client=NoDateMockLLM())
        plan, errors = planner.generate_plan(
            user_query="涨幅前10的股票",
            default_date="20250120"
        )

        # _apply_defaults 应填充日期
        assert plan.get("date") == "20250120"

    def test_default_market_applied(self):
        """测试默认市场是否被正确应用"""
        # 模拟返回空市场，默认值应被应用
        class NoMarketMockLLM:
            def chat(self, *args, **kwargs):
                return json.dumps({
                    "intent": "查询",
                    "date": "20250115",
                    "select_fields": ["SecurityID"],
                    "limit": 10
                })

        planner = LLMQueryPlanner(llm_client=NoMarketMockLLM())
        plan, errors = planner.generate_plan(
            user_query="涨幅前10",
            default_market="XSHG"
        )

        # _apply_defaults 应填充市场
        assert plan.get("market") == "XSHG"

    def test_default_limit_applied(self, planner):
        """测试默认 limit 是否被正确应用"""
        plan, errors = planner.generate_plan(
            user_query="涨幅前10",
            default_date="20250115"
        )

        assert plan.get("limit") is not None
        assert plan.get("limit") > 0


# ============================================================================
# 测试：验证逻辑
# ============================================================================

class TestPlanValidation:
    """测试计划验证逻辑"""

    def test_validate_valid_plan(self, planner):
        """测试有效计划通过验证"""
        plan, errors = planner.generate_plan(
            user_query="涨幅前10的股票",
            default_date="20250115"
        )

        assert errors == []

    def test_validate_invalid_field(self, planner):
        """测试验证能捕获无效字段"""
        # 创建返回无效字段的计划
        class InvalidFieldLLM:
            def chat(self, *args, **kwargs):
                return json.dumps({
                    "date": "20250115",
                    "market": "ALL",
                    "select_fields": ["InvalidField"],
                    "metrics": [],
                    "limit": 10
                })

        bad_planner = LLMQueryPlanner(llm_client=InvalidFieldLLM())
        plan, errors = bad_planner.generate_plan("test query")

        assert len(errors) > 0
        assert any("白名单" in err for err in errors)

    def test_validate_invalid_date_format(self, planner):
        """测试验证能捕获无效日期格式"""
        class BadDateLLM:
            def chat(self, *args, **kwargs):
                return json.dumps({
                    "date": "2025-01-15",  # 错误格式
                    "market": "ALL",
                    "select_fields": ["SecurityID"],
                    "limit": 10
                })

        bad_planner = LLMQueryPlanner(llm_client=BadDateLLM())
        plan, errors = bad_planner.generate_plan("test query")

        assert len(errors) > 0
        assert any("日期" in err for err in errors)

    def test_validate_invalid_market(self, planner):
        """测试验证能捕获无效市场代码"""
        class BadMarketLLM:
            def chat(self, *args, **kwargs):
                return json.dumps({
                    "date": "20250115",
                    "market": "NYSE",  # 无效市场
                    "select_fields": ["SecurityID"],
                    "limit": 10
                })

        bad_planner = LLMQueryPlanner(llm_client=BadMarketLLM())
        plan, errors = bad_planner.generate_plan("test query")

        assert len(errors) > 0
        assert any("市场" in err for err in errors)


# ============================================================================
# 测试：JSON 解析
# ============================================================================

class TestJSONParsing:
    """测试从 LLM 响应中解析 JSON"""

    def test_parse_clean_json(self, planner):
        """测试解析干净的 JSON 响应"""
        plan, errors = planner.generate_plan("涨幅前10")
        assert plan is not None
        assert "error" not in plan

    def test_parse_json_with_markdown(self):
        """测试解析带有 markdown 代码块的 JSON"""
        class MarkdownLLM:
            def chat(self, *args, **kwargs):
                return """```json
{
    "date": "20250115",
    "market": "ALL",
    "select_fields": ["SecurityID"],
    "limit": 10
}
```"""

        planner = LLMQueryPlanner(llm_client=MarkdownLLM())
        plan, errors = planner.generate_plan("test")

        assert plan is not None
        assert plan.get("date") == "20250115"

    def test_parse_json_with_extra_text(self):
        """测试解析带有额外文本的 JSON"""
        class ExtraTextLLM:
            def chat(self, *args, **kwargs):
                return """这是计划:
{"date": "20250115", "market": "ALL", "select_fields": ["SecurityID"], "limit": 10}
希望对你有帮助!"""

        planner = LLMQueryPlanner(llm_client=ExtraTextLLM())
        plan, errors = planner.generate_plan("test")

        assert plan is not None
        assert plan.get("date") == "20250115"


# ============================================================================
# 测试：与 SQL 编译器集成
# ============================================================================

class TestSQLIntegration:
    """测试与 SQL 编译器的集成"""

    def test_plan_to_sql_basic(self, planner, sql_compiler):
        """测试生成的计划可以编译为 SQL"""
        plan, errors = planner.generate_plan(
            user_query="涨幅前10的股票",
            default_date="20250115"
        )

        # 为 SQL 编译器添加 query_type
        plan["query_type"] = "basic"

        sql = sql_compiler.compile(plan, ["data/test.parquet"])

        assert sql is not None
        assert "SELECT" in sql
        assert "FROM" in sql
        assert "LIMIT" in sql

    def test_plan_to_sql_with_metrics(self, planner, sql_compiler):
        """测试带指标的 SQL 编译"""
        plan, errors = planner.generate_plan(
            user_query="涨幅前10的股票",
            default_date="20250115"
        )

        plan["query_type"] = "basic"
        sql = sql_compiler.compile(plan, ["data/test.parquet"])

        # 检查指标是否被展开
        assert "涨幅" in sql or "ClosePx" in sql

    def test_plan_to_sql_with_filter(self, planner, sql_compiler):
        """测试带过滤条件的 SQL 编译"""
        plan, errors = planner.generate_plan(
            user_query="成交额超过10亿的股票",
            default_date="20250115"
        )

        plan["query_type"] = "filter"
        sql = sql_compiler.compile(plan, ["data/test.parquet"])

        assert "WHERE" in sql
        assert "TotalValueTrade" in sql


# ============================================================================
# 测试：边界情况
# ============================================================================

class TestEdgeCases:
    """测试边界情况和错误处理"""

    def test_empty_query(self, planner):
        """测试空查询的处理"""
        plan, errors = planner.generate_plan(
            user_query="",
            default_date="20250115"
        )

        # 应该仍然返回带有默认值的计划
        assert plan is not None
        assert plan.get("date") == "20250115"

    def test_llm_failure(self):
        """测试 LLM 失败的处理"""
        class FailingLLM:
            def chat(self, *args, **kwargs):
                raise Exception("LLM 服务不可用")

        planner = LLMQueryPlanner(llm_client=FailingLLM())
        plan, errors = planner.generate_plan("test query")

        assert len(errors) > 0
        assert "失败" in errors[0] or "error" in plan

    def test_invalid_json_response(self):
        """测试无效 JSON 响应的处理"""
        class BadJSONLLM:
            def chat(self, *args, **kwargs):
                return "这根本不是有效的 JSON"

        planner = LLMQueryPlanner(llm_client=BadJSONLLM())
        plan, errors = planner.generate_plan("test query")

        assert len(errors) > 0

    def test_context_passed_to_llm(self):
        """测试上下文是否传递给 LLM"""
        class ContextCheckLLM:
            def __init__(self):
                self.received_prompt = None

            def chat(self, prompt, *args, **kwargs):
                self.received_prompt = prompt
                return json.dumps({
                    "date": "20250115",
                    "market": "ALL",
                    "select_fields": ["SecurityID"],
                    "limit": 10
                })

        llm = ContextCheckLLM()
        planner = LLMQueryPlanner(llm_client=llm)
        planner.generate_plan(
            user_query="test",
            context={"previous_query": "涨幅"}
        )

        assert "previous_query" in llm.received_prompt


# ============================================================================
# 测试：便捷函数
# ============================================================================

class TestConvenienceFunction:
    """测试 generate_query_plan 便捷函数"""

    def test_generate_query_plan_function(self, mock_llm_client):
        """测试便捷函数"""
        with patch('core.llm_planner.LLMClient', return_value=mock_llm_client):
            plan, errors = generate_query_plan(
                user_query="涨幅前10",
                default_date="20250115",
                llm_client=mock_llm_client
            )

            assert plan is not None
            assert plan.get("date") == "20250115"


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
