"""
SQL 编译器单元测试
==================

测试内容：
1. QueryPlan → SQL 编译
2. 列裁剪
3. WHERE 子句生成
4. ORDER BY 子句生成
5. LIMIT 子句生成
6. 衍生指标计算
"""

import pytest
from core.sql_compiler import SQLCompilerEnhanced as SQLCompiler

# ============================================================================
# 测试用例
# ============================================================================

class TestSQLCompiler:
    """SQL 编译器测试类"""

    def setup_method(self):
        """每个测试方法前执行：初始化编译器"""
        self.compiler = SQLCompiler()

    def test_basic_query(self):
        """
        测试基本查询

        验证 SELECT 字段和 LIMIT 子句正确生成
        """
        query_plan = {
            "query_type": "basic",
            "date": "20250115",
            "market": "HK",
            "metrics": [],
            "filters": [],
            "order_by": [],
            "limit": 10,
            "select_fields": ["SecurityID", "ClosePx"],
        }

        parquet_paths = ["data/test.parquet"]

        sql = self.compiler.compile(query_plan, parquet_paths)

        # 断言：SQL 包含 SELECT SecurityID, ClosePx
        assert "SecurityID" in sql
        assert "ClosePx" in sql
        assert "LIMIT 10" in sql

    def test_filter_clause(self):
        """
        测试 WHERE 子句生成

        验证过滤条件正确生成
        """
        query_plan = {
            "query_type": "filter",
            "date": "20250115",
            "market": "ALL",
            "metrics": [],
            "filters": [
                {"field": "TotalValueTrade", "op": ">", "value": 1000000}
            ],
            "order_by": [],
            "limit": 10,
            "select_fields": ["SecurityID", "TotalValueTrade"],
        }

        parquet_paths = ["data/test.parquet"]

        sql = self.compiler.compile(query_plan, parquet_paths)

        # 断言：SQL 包含 WHERE TotalValueTrade > 1000000
        assert "WHERE" in sql
        assert "TotalValueTrade" in sql
        assert "> 1000000" in sql

    def test_order_by_clause(self):
        """
        测试 ORDER BY 子句生成

        验证排序条件正确生成（包含衍生指标）
        """
        query_plan = {
            "query_type": "basic",
            "date": "20250115",
            "market": "ALL",
            "metrics": ["涨幅"],
            "filters": [],
            "order_by": [{"field": "涨幅", "desc": True}],
            "limit": 10,
            "select_fields": ["SecurityID", "涨幅"],
        }

        parquet_paths = ["data/test.parquet"]

        sql = self.compiler.compile(query_plan, parquet_paths)

        # 断言：SQL 包含 ORDER BY 涨幅 DESC
        assert "ORDER BY" in sql
        assert "涨幅" in sql
        assert "DESC" in sql

    def test_derived_metrics(self):
        """
        测试衍生指标计算

        验证衍生指标（涨幅、振幅）正确展开为 SQL 表达式
        """
        query_plan = {
            "query_type": "basic",
            "date": "20250115",
            "market": "ALL",
            "metrics": ["涨幅", "振幅"],
            "filters": [],
            "order_by": [],
            "limit": 10,
            "select_fields": ["SecurityID", "涨幅", "振幅"],
        }

        parquet_paths = ["data/test.parquet"]

        sql = self.compiler.compile(query_plan, parquet_paths)

        # 断言：SQL 包含涨幅和振幅的计算表达式
        assert "涨幅" in sql
        assert "振幅" in sql
        # 涨幅计算：(ClosePx - PreClosePx) / PreClosePx * 100
        assert "ClosePx" in sql
        assert "PreClosePx" in sql
        # 振幅计算：(HighPx - LowPx) / PreClosePx * 100
        assert "HighPx" in sql
        assert "LowPx" in sql

    def test_aggregation_query(self):
        """
        测试聚合查询

        验证 GROUP BY 和聚合函数正确生成
        """
        query_plan = {
            "query_type": "stats",
            "date": "20250115",
            "market": "ALL",
            "metrics": [],
            "filters": [],
            "order_by": [],
            "limit": 10,
            "select_fields": [],
            "aggregations": [
                {"func": "sum", "field": "TotalValueTrade", "alias": "总成交额"},
                {"func": "count", "field": "*", "alias": "股票数量"}
            ],
            "group_by": [],
        }

        parquet_paths = ["data/test.parquet"]

        sql = self.compiler.compile(query_plan, parquet_paths)

        # 断言：SQL 包含聚合函数
        assert "SUM" in sql
        assert "COUNT" in sql
        assert "总成交额" in sql
        assert "股票数量" in sql

    def test_group_by_query(self):
        """
        测试分组统计查询

        验证 GROUP BY 子句和分组聚合正确生成
        """
        query_plan = {
            "query_type": "stats",
            "date": "20250115",
            "market": "ALL",
            "metrics": ["涨幅"],
            "filters": [],
            "order_by": [{"field": "平均涨幅", "desc": True}],
            "limit": 10,
            "select_fields": ["价格区间"],
            "aggregations": [
                {"func": "count", "field": "*", "alias": "股票数量"},
                {"func": "avg", "field": "涨幅", "alias": "平均涨幅"}
            ],
            "group_by": ["价格区间"],
        }

        parquet_paths = ["data/test.parquet"]

        sql = self.compiler.compile(query_plan, parquet_paths)

        # 断言：SQL 包含 GROUP BY
        assert "GROUP BY" in sql
        assert "价格区间" in sql
        assert "AVG" in sql
        assert "平均涨幅" in sql

    def test_multiple_parquet_files(self):
        """
        测试多个 Parquet 文件

        验证 UNION ALL 正确生成
        """
        query_plan = {
            "query_type": "basic",
            "date": "20250115",
            "market": "ALL",
            "metrics": [],
            "filters": [],
            "order_by": [],
            "limit": 10,
            "select_fields": ["SecurityID", "ClosePx"],
        }

        parquet_paths = ["data/test1.parquet", "data/test2.parquet"]

        sql = self.compiler.compile(query_plan, parquet_paths)

        # 断言：SQL 包含 UNION ALL
        assert "UNION ALL" in sql
        assert "test1.parquet" in sql
        assert "test2.parquet" in sql

    def test_snapshot_dedup(self):
        """
        测试快照去重

        验证使用 ROW_NUMBER() 选择最新快照
        """
        query_plan = {
            "query_type": "basic",
            "date": "20250115",
            "market": "ALL",
            "metrics": [],
            "filters": [],
            "order_by": [],
            "limit": 10,
            "select_fields": ["SecurityID", "ClosePx"],
        }

        parquet_paths = ["data/test.parquet"]

        sql = self.compiler.compile(query_plan, parquet_paths)

        # 断言：SQL 包含快照去重逻辑
        assert "ROW_NUMBER()" in sql
        assert "PARTITION BY SecurityID" in sql
        assert "ORDER BY MDTime DESC" in sql
        assert "rn = 1" in sql


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
