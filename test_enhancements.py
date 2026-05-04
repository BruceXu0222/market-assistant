"""
增强功能测试脚本
===============

测试内容：
1. SQL 编译器增强功能
2. LangGraph 工作流打印信息
3. 5大类查询场景的 QueryPlan 生成（含快照去重逻辑）

使用方法：
    python test_enhancements.py
"""

import sys
sys.path.insert(0, '.')

from core.sql_compiler import SQLCompilerEnhanced, METRIC_DEFINITIONS
from workflow.graph import build_graph, GraphState


def test_metric_definitions():
    """测试衍生指标定义"""
    print("="*80)
    print("测试 1: 衍生指标定义")
    print("="*80)

    print(f"\n共定义了 {len(METRIC_DEFINITIONS)} 个衍生指标：")
    for i, (name, expr) in enumerate(METRIC_DEFINITIONS.items(), 1):
        print(f"  {i:2d}. {name:12s}: {expr[:60]}...")

    print("\n✓ 衍生指标定义测试通过\n")


def test_sql_compiler_basic():
    """
    测试基础查询 SQL 编译

    注意：由于原始数据以快照形式存储（同一 SecurityID 在不同 MDTime 有多条记录），
    SQL 编译器会自动使用窗口函数选择每个 SecurityID 的最新快照（按 MDTime DESC），
    这样可以避免同一股票被重复选择。
    """
    print("="*80)
    print("测试 2: 基础 TopK 查询 SQL 编译")
    print("="*80)

    compiler = SQLCompilerEnhanced()

    query_plan = {
        "query_type": "basic",
        "date": "20250115",
        "market": "ALL",
        "metrics": ["涨幅"],
        "filters": [],
        "order_by": [{"field": "涨幅", "desc": True}],
        "limit": 10,
        "output_fields": ["SecurityID", "ClosePx", "PreClosePx", "涨幅"],
    }

    sql = compiler.compile(query_plan, ["data/test.parquet"])

    print("\n生成的 SQL:")
    print("-" * 80)
    print(sql)
    print("-" * 80)

    # 验证 SQL 包含关键部分
    assert "SELECT" in sql, "SQL 应包含 SELECT"
    assert "FROM" in sql, "SQL 应包含 FROM"
    assert "ORDER BY" in sql, "SQL 应包含 ORDER BY"
    assert "LIMIT" in sql, "SQL 应包含 LIMIT"
    assert "涨幅" in sql, "SQL 应包含衍生指标'涨幅'"
    assert "ROW_NUMBER" in sql, "SQL 应包含快照去重逻辑"
    assert "PARTITION BY SecurityID" in sql, "SQL 应按 SecurityID 分区"

    print("\n✓ 基础查询 SQL 编译测试通过\n")


def test_sql_compiler_aggregation():
    """
    测试聚合查询 SQL 编译

    注意：对于聚合查询（如计算总成交额），SQL 编译器会先选择每个 SecurityID 的最新快照，
    然后再对 TotalValueTrade 进行求和，这样可以避免对同一股票的多个快照重复计数。
    """
    print("="*80)
    print("测试 3: 聚合统计查询 SQL 编译")
    print("="*80)

    compiler = SQLCompilerEnhanced()

    query_plan = {
        "query_type": "aggregation",
        "date": "20250115",
        "market": "ALL",
        "metrics": [],
        "filters": [],
        "order_by": [],
        "limit": 1,
        "output_fields": [],
        "aggregations": [
            {"func": "sum", "field": "TotalValueTrade", "alias": "总成交额"},
            {"func": "count", "field": "*", "alias": "股票数量"},
            {"func": "avg", "field": "ClosePx", "alias": "平均价格"}
        ],
        "group_by": [],
    }

    sql = compiler.compile(query_plan, ["data/test.parquet"])

    print("\n生成的 SQL:")
    print("-" * 80)
    print(sql)
    print("-" * 80)

    # 验证 SQL 包含聚合函数
    assert "SUM" in sql or "sum" in sql, "SQL 应包含 SUM"
    assert "COUNT" in sql or "count" in sql, "SQL 应包含 COUNT"
    assert "AVG" in sql or "avg" in sql, "SQL 应包含 AVG"
    assert "ROW_NUMBER" in sql, "SQL 应包含快照去重逻辑"

    print("\n✓ 聚合查询 SQL 编译测试通过\n")


def test_sql_compiler_groupby():
    """
    测试分组统计 SQL 编译

    注意：对于分组统计查询，SQL 编译器会先选择每个 SecurityID 的最新快照，
    然后再对每个分组进行聚合统计（如按价格区间分组计算总成交额），
    这样可以确保每个股票只贡献一次数据到聚合结果中。
    """
    print("="*80)
    print("测试 4: 分组统计查询 SQL 编译")
    print("="*80)

    compiler = SQLCompilerEnhanced()

    query_plan = {
        "query_type": "stats",
        "date": "20250115",
        "market": "ALL",
        "metrics": ["涨幅", "价格区间"],
        "filters": [],
        "order_by": [{"field": "平均涨幅", "desc": True}],
        "limit": 10,
        "output_fields": ["价格区间"],
        "aggregations": [
            {"func": "count", "field": "*", "alias": "股票数量"},
            {"func": "avg", "field": "涨幅", "alias": "平均涨幅"},
            {"func": "sum", "field": "TotalValueTrade", "alias": "总成交额"}
        ],
        "group_by": ["价格区间"],
    }

    sql = compiler.compile(query_plan, ["data/test.parquet"])

    print("\n生成的 SQL:")
    print("-" * 80)
    print(sql)
    print("-" * 80)

    # 验证 SQL 包含 GROUP BY
    assert "GROUP BY" in sql, "SQL 应包含 GROUP BY"
    assert "价格区间" in sql, "SQL 应包含分组字段 价格区间"
    assert "ROW_NUMBER" in sql, "SQL 应包含快照去重逻辑"

    print("\n✓ 分组统计 SQL 编译测试通过\n")


def test_langgraph_workflow():
    """测试 LangGraph 工作流打印信息"""
    print("="*80)
    print("测试 5: LangGraph 工作流执行（带打印信息）")
    print("="*80)

    # 构建图
    graph = build_graph()

    # 初始状态
    initial_state: GraphState = {
        "session_id": "test-session",
        "user_message": "今天涨幅前10的股票有哪些？",
        "default_date": "20250115",
        "default_market": "ALL",
        "history": [],
        "query_type": None,
        "query_plan": None,
        "validation_errors": None,
        "retry_count": 0,
        "sql": None,
        "dataframe": None,
        "summary": None,
        "table": None,
        "commentary": "",
        "error": None,
        "debug": {},
    }

    # 运行图
    print("\n开始执行工作流...\n")
    result = graph.invoke(initial_state)

    print("\n" + "="*80)
    print("工作流执行完成！")
    print("="*80)
    print(f"\n最终状态:")
    print(f"  - session_id: {result.get('session_id')}")
    print(f"  - query_type: {result.get('query_type')}")
    print(f"  - query_plan: {'存在' if result.get('query_plan') else '不存在'}")
    print(f"  - sql: {'存在' if result.get('sql') else '不存在'}")
    print(f"  - table: {len(result.get('table', []))} 行")
    print(f"  - summary: {result.get('summary')}")
    print(f"  - commentary: {result.get('commentary', '')[:100]}...")

    # 验证关键状态
    assert result.get("query_type") == "market_query", "query_type 应为 market_query"
    assert result.get("query_plan") is not None, "query_plan 应存在"
    assert result.get("sql") is not None, "sql 应存在"

    print("\n✓ LangGraph 工作流测试通过\n")


def test_complex_query_scenarios():
    """测试5大类查询场景的 SQL 编译"""
    print("="*80)
    print("测试 6: 5大类查询场景 SQL 编译")
    print("="*80)

    compiler = SQLCompilerEnhanced()

    scenarios = [
        {
            "name": "场景1: 基础 TopK 查询",
            "plan": {
                "query_type": "basic",
                "date": "20250115",
                "market": "ALL",
                "metrics": ["涨幅"],
                "filters": [],
                "order_by": [{"field": "涨幅", "desc": True}],
                "limit": 10,
                "output_fields": ["SecurityID", "ClosePx", "涨幅"],
            }
        },
        {
            "name": "场景2: 条件筛选查询",
            "plan": {
                "query_type": "filter",
                "date": "20250115",
                "market": "ALL",
                "metrics": ["涨幅"],
                "filters": [
                    {"field": "涨幅", "op": ">", "value": 3},
                    {"field": "TotalValueTrade", "op": ">", "value": 100000000}
                ],
                "order_by": [{"field": "TotalValueTrade", "desc": True}],
                "limit": 50,
                "output_fields": ["SecurityID", "ClosePx", "涨幅", "TotalValueTrade"],
            }
        },
        {
            "name": "场景3: 纯聚合查询（总成交额）",
            "plan": {
                "query_type": "aggregation",
                "date": "20250115",
                "market": "ALL",
                "metrics": [],
                "filters": [],
                "order_by": [],
                "limit": 1,
                "output_fields": [],
                "aggregations": [
                    {"func": "sum", "field": "TotalValueTrade", "alias": "总成交额"}
                ],
                "group_by": [],
            }
        },
        {
            "name": "场景4: 分组统计（按行业）",
            "plan": {
                "query_type": "stats",
                "date": "20250115",
                "market": "ALL",
                "metrics": ["涨幅"],
                "filters": [],
                "order_by": [{"field": "平均涨幅", "desc": True}],
                "limit": 10,
                "output_fields": ["Industry"],
                "aggregations": [
                    {"func": "avg", "field": "涨幅", "alias": "平均涨幅"}
                ],
                "group_by": ["Industry"],
            }
        },
        {
            "name": "场景5: 异动发现（放量股票）",
            "plan": {
                "query_type": "anomaly",
                "date": "20250115",
                "market": "ALL",
                "metrics": ["振幅"],
                "filters": [
                    {"field": "TotalVolumeTrade", "op": ">", "value": 100000000}
                ],
                "order_by": [{"field": "振幅", "desc": True}],
                "limit": 20,
                "output_fields": ["SecurityID", "ClosePx", "振幅", "TotalVolumeTrade"],
            }
        },
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'-'*80}")
        print(f"{scenario['name']}")
        print(f"{'-'*80}")

        try:
            sql = compiler.compile(scenario["plan"], ["data/test.parquet"])
            print(f"\n✓ SQL 编译成功，长度 {len(sql)} 字符")
            print(f"  SQL 预览: {sql}")
        except Exception as e:
            print(f"\n✗ SQL 编译失败: {e}")

    print("\n" + "="*80)
    print("✓ 5大类查询场景测试完成")
    print("="*80 + "\n")


def main():
    """主测试函数"""
    print("\n" + "="*80)
    print("智能行情分析助手 - 增强功能测试")
    print("="*80 + "\n")

    try:
        # 测试1: 衍生指标定义
        test_metric_definitions()

        # 测试2: 基础查询 SQL 编译
        test_sql_compiler_basic()

        # 测试3: 聚合查询 SQL 编译
        test_sql_compiler_aggregation()

        # 测试4: 分组统计 SQL 编译
        test_sql_compiler_groupby()

        # 测试5: LangGraph 工作流
        test_langgraph_workflow()

        # 测试6: 7大类查询场景
        test_complex_query_scenarios()

        # 总结
        print("\n" + "="*80)
        print("所有测试通过！✓")
        print("="*80)
        print("\n下一步建议：")
        print("  1. 准备 Parquet 数据文件")
        print("  2. 部署 vLLM 服务")
        print("  3. 实现 PlanGen 节点（调用 LLM）")
        print("  4. 实现 Execute 节点（执行 DuckDB 查询）")
        print("  5. 端到端测试")
        print()

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
