"""
Execute 节点：SQL 执行
=====================

功能：
1. 编译 QueryPlan 为 SQL
2. 解析数据文件路径（基于 date/market）
3. 执行 DuckDB 查询
4. 返回 DataFrame

关键点：
1. 所有数值计算由 SQL 完成（杜绝 LLM 幻觉）
2. 列裁剪：只 SELECT 必要列
3. 先过滤后排序：减少排序数据量
4. TopK 优化：ORDER BY ... LIMIT k
"""

from typing import Dict, Any
import time

from core.sql_compiler import SQLCompilerEnhanced
from core.duckdb_engine import DuckDBEngine
from core.path_resolver import resolve_parquet_paths

# ============================================================================
# 执行函数
# ============================================================================

def execute_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行节点：QueryPlan → SQL → DuckDB → DataFrame

    Args:
        state: LangGraph 状态

    Returns:
        state: 更新后的状态（包含 sql, dataframe）

    TODO:
    1. 编译 QueryPlan 为 SQL
    2. 解析 Parquet 文件路径
    3. 执行 DuckDB 查询
    4. 处理异常（文件不存在、SQL 错误等）
    5. 记录延迟
    """

    query_plan = state.get("query_plan")

    if not query_plan:
        state["error"] = "QueryPlan 为空，无法执行"
        return state

    start_time = time.time()

    # ========================================================================
    # 1. 解析 Parquet 文件路径
    # ========================================================================

    try:
        date = query_plan.get("date")
        market = query_plan.get("market", "ALL")
        paths = resolve_parquet_paths(date, market)
    except Exception as e:
        state["error"] = f"未找到数据文件: date={query_plan.get('date')}, market={query_plan.get('market')}: {e}"
        return state

    # ========================================================================
    # 2. 编译 QueryPlan 为 SQL
    # ========================================================================

    try:
        compiler = SQLCompilerEnhanced()
        sql = compiler.compile(query_plan, paths)
        state["sql"] = sql
    except Exception as e:
        state["error"] = f"SQL 编译失败: {e}"
        return state

    # ========================================================================
    # 3. 执行 DuckDB 查询
    # ========================================================================

    with DuckDBEngine() as engine:
        try:
            state["dataframe"] = engine.execute(sql)
        except Exception as e:
            state["error"] = f"DuckDB 查询失败: {e}"
            return state

    # ========================================================================
    # 4. 记录延迟
    # ========================================================================

    elapsed_ms = (time.time() - start_time) * 1000
    state.setdefault("debug", {}).setdefault("latency_ms", {})["execute"] = elapsed_ms

    # ========================================================================
    # 日志记录
    # ========================================================================

    # TODO: 添加日志
    # logger.info(f"[Execute] session={state['session_id']}, rows={len(df)}, latency={elapsed_ms}ms")

    return state
