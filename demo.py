"""
市场助手演示脚本
================

演示完整的查询流程：
1. 用户输入自然语言问题
2. LangGraph 工作流执行
3. 返回查询结果和解读

使用方法：
    python demo.py
"""

import sys
sys.path.insert(0, '.')

from workflow.graph import build_graph, GraphState
import json


def demo_query(user_message: str, date: str = "20250115"):
    """
    演示单个查询

    Args:
        user_message: 用户问题
        date: 查询日期
    """

    print("\n" + "="*80)
    print(f"用户问题: {user_message}")
    print("="*80)

    # 构建图
    graph = build_graph()

    # 初始状态
    initial_state: GraphState = {
        "session_id": "demo-session",
        "user_message": user_message,
        "default_date": date,
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
    result = graph.invoke(initial_state)

    # 显示结果
    print("\n" + "="*80)
    print("查询结果")
    print("="*80)

    if result.get("error"):
        print(f"❌ 查询失败: {result['error']}")
        return

    # 显示查询计划
    print(f"\n📋 查询计划:")
    print(f"  类型: {result['query_plan']['query_type']}")
    print(f"  日期: {result['query_plan']['date']}")
    print(f"  排序: {result['query_plan']['order_by']}")
    print(f"  限制: {result['query_plan']['limit']}")

    # 显示 SQL
    print(f"\n🔍 生成的 SQL:")
    sql_lines = result['sql'].split('\n')
    for line in sql_lines[:10]:  # 只显示前10行
        print(f"  {line}")
    if len(sql_lines) > 10:
        print(f"  ... ({len(sql_lines) - 10} more lines)")

    # 显示数据
    print(f"\n📊 查询结果:")
    print(f"  总记录数: {result['summary']['总记录数']}")

    if result['table']:
        print(f"\n前 5 条记录:")
        for i, row in enumerate(result['table'][:5], 1):
            print(f"\n  记录 {i}:")
            for k, v in row.items():
                if isinstance(v, float):
                    print(f"    {k}: {v:.2f}")
                else:
                    print(f"    {k}: {v}")

    # 显示解读
    print(f"\n💬 专业解读:")
    print(f"  {result['commentary']}")

    print("\n" + "="*80 + "\n")


def main():
    """主函数"""

    print("="*80)
    print("智能市场助手 - 演示")
    print("="*80)
    print("\n使用 Mock 数据演示完整查询流程\n")

    # 演示场景 1: 涨幅查询
    demo_query("今天涨幅前10的股票有哪些？")

    # 演示场景 2: 成交额查询
    demo_query("成交额最大的10只股票是什么？")

    # 演示场景 3: 振幅查询
    demo_query("振幅最大的股票有哪些？")

    print("="*80)
    print("演示完成！")
    print("="*80)
    print("\n下一步:")
    print("  1. 准备真实的 Parquet 数据文件")
    print("  2. 部署 vLLM 服务")
    print("  3. 实现真实的 PlanGen 节点（调用 LLM）")
    print("  4. 实现 Narrate 节点（调用 LLM 生成解读）")
    print("  5. 完善校验和修复逻辑")
    print()


if __name__ == "__main__":
    main()
