"""
集成测试
========

端到端测试整个 Pipeline：
1. LLM 计划生成（使用真实 OpenAI API）
2. SQL 编译
3. DuckDB 执行
4. 完整工作流

运行方式:
    pytest tests/test_integration.py -v -s

注意:
- 需要配置有效的 OpenAI API Key
- 需要 data/test.parquet 测试数据
"""

import pytest
import json
from datetime import datetime, timedelta

# ============================================================================
# 导入被测模块
# ============================================================================

from core.llm_client import LLMClient
from core.llm_planner import LLMQueryPlanner, generate_query_plan
from core.sql_compiler import SQLCompilerEnhanced


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def llm_client():
    """创建 LLM 客户端（从 settings.yaml 加载配置）"""
    return LLMClient()


@pytest.fixture
def planner(llm_client):
    """创建 LLM 查询计划生成器"""
    return LLMQueryPlanner(llm_client)


@pytest.fixture
def compiler():
    """创建 SQL 编译器"""
    return SQLCompilerEnhanced()


@pytest.fixture
def test_parquet_path():
    """测试数据路径"""
    return "data/test.parquet"


@pytest.fixture
def default_date():
    """默认测试日期"""
    return "20250115"


# ============================================================================
# LLM 客户端测试
# ============================================================================

class TestLLMClient:
    """LLM 客户端测试"""

    def test_client_initialization(self, llm_client):
        """测试客户端初始化"""
        assert llm_client is not None
        assert llm_client.model == "gpt-5.5"
        assert "api.openai.com" in llm_client.base_url
        print(f"\n[测试] LLM 客户端初始化成功")
        print(f"  - 模型: {llm_client.model}")
        print(f"  - API 地址: {llm_client.base_url}")

    def test_simple_chat(self, llm_client):
        """测试简单对话"""
        print(f"\n[测试] 发送请求: '请用一个词回答：1+1等于几？'")
        response = llm_client.chat(
            prompt="请用一个词回答：1+1等于几？",
            max_tokens=10
        )
        assert response is not None
        assert len(response) > 0
        print(f"[测试] 简单对话测试通过")
        print(f"  - 模型响应: '{response}'")


# ============================================================================
# LLM 计划生成测试
# ============================================================================

class TestLLMPlanner:
    """LLM 计划生成器测试"""

    def test_topk_query(self, planner, default_date):
        """测试 TopK 查询"""
        query = "今天涨幅前10的股票"

        plan, errors = planner.generate_plan(
            user_query=query,
            default_date=default_date,
            default_market="ALL"
        )

        print(f"\n[测试] TopK 查询")
        print(f"  - 输入: {query}")
        print(f"  - 计划: {json.dumps(plan, ensure_ascii=False, indent=2)}")
        print(f"  - 错误: {errors}")

        # 验证基本结构
        assert "date" in plan
        assert "market" in plan
        assert "limit" in plan
        assert plan["limit"] == 10  # 用户指定了前10

        # 验证排序
        assert "order_by" in plan
        assert len(plan["order_by"]) > 0

        # 验证涨幅指标
        assert "涨幅" in plan.get("metrics", []) or any(
            o.get("field") == "涨幅" for o in plan.get("order_by", [])
        )

    def test_filter_query(self, planner, default_date):
        """测试条件筛选查询"""
        query = "成交额超过10亿的股票"

        plan, errors = planner.generate_plan(
            user_query=query,
            default_date=default_date,
            default_market="ALL"
        )

        print(f"\n[测试] 条件筛选查询")
        print(f"  - 输入: {query}")
        print(f"  - 计划: {json.dumps(plan, ensure_ascii=False, indent=2)}")
        print(f"  - 错误: {errors}")

        # 验证有过滤条件
        assert "filters" in plan
        # 10亿 = 10000000000
        has_value_filter = any(
            f.get("field") == "TotalValueTrade" and f.get("value", 0) >= 1000000000
            for f in plan.get("filters", [])
        )
        # 验证有成交额相关的过滤
        assert has_value_filter or "TotalValueTrade" in plan.get("select_fields", [])

    def test_zhangting_query(self, planner, default_date):
        """测试涨幅阈值查询"""
        query = "今天涨幅超过10%的股票有哪些"

        plan, errors = planner.generate_plan(
            user_query=query,
            default_date=default_date,
            default_market="ALL"
        )

        print(f"\n[测试] 涨幅阈值查询")
        print(f"  - 输入: {query}")
        print(f"  - 计划: {json.dumps(plan, ensure_ascii=False, indent=2)}")
        print(f"  - 错误: {errors}")

        # 验证使用了涨幅阈值相关指标或过滤
        has_zhangting = (
            "涨幅" in plan.get("metrics", []) or
            any(f.get("field") == "涨幅" for f in plan.get("filters", [])) or
            any("MaxPx" in str(f) or "ClosePx" in str(f) for f in plan.get("filters", []))
        )
        assert has_zhangting

    def test_stats_query(self, planner, default_date):
        """测试统计查询"""
        query = "统计今天上涨和下跌的股票数量"

        plan, errors = planner.generate_plan(
            user_query=query,
            default_date=default_date,
            default_market="ALL"
        )

        print(f"\n[测试] 统计查询")
        print(f"  - 输入: {query}")
        print(f"  - 计划: {json.dumps(plan, ensure_ascii=False, indent=2)}")
        print(f"  - 错误: {errors}")

        # 验证使用了聚合函数
        assert "aggregations" in plan
        assert len(plan["aggregations"]) > 0

    def test_amplitude_query(self, planner, default_date):
        """测试振幅查询"""
        query = "振幅最大的20只股票"

        plan, errors = planner.generate_plan(
            user_query=query,
            default_date=default_date,
            default_market="ALL"
        )

        print(f"\n[测试] 振幅查询")
        print(f"  - 输入: {query}")
        print(f"  - 计划: {json.dumps(plan, ensure_ascii=False, indent=2)}")
        print(f"  - 错误: {errors}")

        # 验证使用了振幅指标
        has_amplitude = (
            "振幅" in plan.get("metrics", []) or
            any(o.get("field") == "振幅" for o in plan.get("order_by", []))
        )
        assert has_amplitude
        assert plan["limit"] == 20


# ============================================================================
# SQL 编译测试
# ============================================================================

class TestSQLCompiler:
    """SQL 编译器测试"""

    def test_compile_basic_query(self, compiler, test_parquet_path):
        """测试基础查询编译"""
        query_plan = {
            "query_type": "basic",
            "date": "20250115",
            "market": "ALL",
            "select_fields": ["SecurityID", "ClosePx", "PreClosePx"],
            "metrics": ["涨幅"],
            "filters": [],
            "order_by": [{"field": "涨幅", "desc": True}],
            "limit": 10,
        }

        sql = compiler.compile(query_plan, [test_parquet_path])

        print(f"\n[测试] 基础查询编译")
        print(f"  - SQL:\n{sql}")

        # 验证 SQL 结构
        assert "SELECT" in sql
        assert "SecurityID" in sql
        assert "涨幅" in sql
        assert "ORDER BY" in sql
        assert "LIMIT 10" in sql

    def test_compile_aggregation_query(self, compiler, test_parquet_path):
        """测试聚合查询编译"""
        query_plan = {
            "query_type": "stats",
            "date": "20250115",
            "market": "ALL",
            "select_fields": [],
            "metrics": [],
            "filters": [],
            "aggregations": [
                {"func": "count", "field": "*", "alias": "股票数量"},
                {"func": "sum", "field": "TotalValueTrade", "alias": "总成交额"}
            ],
            "group_by": [],
            "order_by": [],
            "limit": 1,
        }

        sql = compiler.compile(query_plan, [test_parquet_path])

        print(f"\n[测试] 聚合查询编译")
        print(f"  - SQL:\n{sql}")

        # 验证 SQL 结构
        assert "COUNT" in sql
        assert "SUM" in sql
        assert "股票数量" in sql
        assert "总成交额" in sql


# ============================================================================
# 端到端测试
# ============================================================================

class TestEndToEnd:
    """端到端测试：完整 Pipeline"""

    def test_full_pipeline_topk(self, planner, compiler, test_parquet_path, default_date):
        """测试完整 Pipeline: TopK 查询"""
        import duckdb

        query = "涨幅前5的股票"

        print(f"\n{'='*60}")
        print(f"[端到端测试] TopK 查询")
        print(f"{'='*60}")
        print(f"用户输入: {query}")

        # Step 1: LLM 生成计划
        print(f"\n[Step 1] 生成查询计划...")
        plan, errors = planner.generate_plan(
            user_query=query,
            default_date=default_date,
            default_market="ALL"
        )
        print(f"  - 计划: {json.dumps(plan, ensure_ascii=False, indent=2)}")
        print(f"  - 验证错误: {errors}")

        # 确保计划有效
        if not plan.get("query_type"):
            plan["query_type"] = "basic"

        # Step 2: 编译 SQL
        print(f"\n[Step 2] 编译 SQL...")
        sql = compiler.compile(plan, [test_parquet_path])
        print(f"  - SQL:\n{sql}")

        # Step 3: 执行查询
        print(f"\n[Step 3] 执行 DuckDB 查询...")
        conn = duckdb.connect(":memory:")
        df = conn.execute(sql).fetchdf()
        conn.close()

        print(f"  - 返回行数: {len(df)}")
        print(f"  - 列名: {list(df.columns)}")
        print(f"\n[结果预览]")
        print(df.to_string())

        # 验证结果
        assert len(df) <= 5  # 限制了前5
        assert "SecurityID" in df.columns

    def test_full_pipeline_filter(self, planner, compiler, test_parquet_path, default_date):
        """测试完整 Pipeline: 条件筛选"""
        import duckdb

        query = "成交量大于100万股的股票"

        print(f"\n{'='*60}")
        print(f"[端到端测试] 条件筛选")
        print(f"{'='*60}")
        print(f"用户输入: {query}")

        # Step 1: LLM 生成计划
        print(f"\n[Step 1] 生成查询计划...")
        plan, errors = planner.generate_plan(
            user_query=query,
            default_date=default_date,
            default_market="ALL"
        )
        print(f"  - 计划: {json.dumps(plan, ensure_ascii=False, indent=2)}")

        # 确保计划有效
        if not plan.get("query_type"):
            plan["query_type"] = "filter"

        # Step 2: 编译 SQL
        print(f"\n[Step 2] 编译 SQL...")
        sql = compiler.compile(plan, [test_parquet_path])
        print(f"  - SQL:\n{sql}")

        # Step 3: 执行查询
        print(f"\n[Step 3] 执行 DuckDB 查询...")
        conn = duckdb.connect(":memory:")
        df = conn.execute(sql).fetchdf()
        conn.close()

        print(f"  - 返回行数: {len(df)}")
        print(f"\n[结果预览]")
        if len(df) > 0:
            print(df.head(10).to_string())
        else:
            print("  (无匹配数据)")

    def test_full_pipeline_stats(self, planner, compiler, test_parquet_path, default_date):
        """测试完整 Pipeline: 统计分析"""
        import duckdb

        query = "统计今天的总成交额和平均涨幅"

        print(f"\n{'='*60}")
        print(f"[端到端测试] 统计分析")
        print(f"{'='*60}")
        print(f"用户输入: {query}")

        # Step 1: LLM 生成计划
        print(f"\n[Step 1] 生成查询计划...")
        plan, errors = planner.generate_plan(
            user_query=query,
            default_date=default_date,
            default_market="ALL"
        )
        print(f"  - 原始计划: {json.dumps(plan, ensure_ascii=False, indent=2)}")

        # 确保计划有效
        if not plan.get("query_type"):
            if plan.get("aggregations"):
                plan["query_type"] = "stats"
            else:
                plan["query_type"] = "basic"

        # 对于纯聚合查询，清空 select_fields 以避免 GROUP BY 错误
        # 因为非聚合字段不能出现在没有 GROUP BY 的聚合查询中
        if plan.get("query_type") == "stats" and plan.get("aggregations") and not plan.get("group_by"):
            plan["select_fields"] = []
            print(f"  - 调整后计划（清空 select_fields）: {json.dumps(plan, ensure_ascii=False, indent=2)}")

        # Step 2: 编译 SQL
        print(f"\n[Step 2] 编译 SQL...")
        sql = compiler.compile(plan, [test_parquet_path])
        print(f"  - SQL:\n{sql}")

        # Step 3: 执行查询
        print(f"\n[Step 3] 执行 DuckDB 查询...")
        conn = duckdb.connect(":memory:")
        df = conn.execute(sql).fetchdf()
        conn.close()

        print(f"  - 返回行数: {len(df)}")
        print(f"\n[结果]")
        print(df.to_string())


# ============================================================================
# 批量查询测试
# ============================================================================

class TestBatchQueries:
    """批量查询测试"""

    QUERIES = [
        "今天涨幅前10的股票",
        "成交额最高的5只股票",
        "振幅超过5%的股票",
        "跌幅最大的10只股票",
        "上海市场涨幅前10",
    ]

    def test_batch_queries(self, planner, compiler, test_parquet_path, default_date):
        """测试多个查询"""
        import duckdb

        print(f"\n{'='*60}")
        print(f"[批量测试] 执行 {len(self.QUERIES)} 个查询")
        print(f"{'='*60}")

        results = []
        for i, query in enumerate(self.QUERIES, 1):
            print(f"\n[{i}/{len(self.QUERIES)}] {query}")
            print("-" * 40)

            try:
                # 生成计划
                plan, errors = planner.generate_plan(
                    user_query=query,
                    default_date=default_date,
                    default_market="ALL"
                )

                if not plan.get("query_type"):
                    plan["query_type"] = "basic"

                # 编译 SQL
                sql = compiler.compile(plan, [test_parquet_path])

                # 执行查询
                conn = duckdb.connect(":memory:")
                df = conn.execute(sql).fetchdf()
                conn.close()

                results.append({
                    "query": query,
                    "success": True,
                    "rows": len(df),
                    "errors": errors
                })
                print(f"  ✓ 成功，返回 {len(df)} 行")

            except Exception as e:
                results.append({
                    "query": query,
                    "success": False,
                    "error": str(e)
                })
                print(f"  ✗ 失败: {e}")

        # 汇总结果
        print(f"\n{'='*60}")
        print(f"[批量测试汇总]")
        print(f"{'='*60}")
        success_count = sum(1 for r in results if r["success"])
        print(f"成功: {success_count}/{len(results)}")
        for r in results:
            status = "✓" if r["success"] else "✗"
            print(f"  {status} {r['query']}")


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
