"""
LangGraph 状态机定义（增强版）
===========================

核心功能：
1. 定义 8 个节点的工作流图
2. 管理节点之间的状态流转
3. 处理正常路径和异常路径
4. **新增：每个节点打印执行信息**

工作流图：
- 正常路径：Router → PlanGen → Validate → Execute → PostProcess → Narrate → MemoryUpdate
- 异常路径：
  - Validate 失败 → Repair → Validate（最多重试 1-2 次）
  - Execute 失败 → Clarify/Repair
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List, Dict, Any, Annotated
import operator

# ============================================================================
# 状态定义
# ============================================================================

class GraphState(TypedDict):
    """LangGraph 状态定义（增强版）"""

    # 会话信息
    session_id: str
    user_message: str
    default_date: Optional[str]
    default_market: str
    history: Annotated[List[Dict[str, str]], operator.add]

    # 路由信息
    query_type: Optional[str]

    # 计划信息
    query_plan: Optional[Dict[str, Any]]
    validation_errors: Optional[List[str]]
    retry_count: int

    # 执行信息
    sql: Optional[str]
    dataframe: Optional[Any]

    # 输出信息
    summary: Optional[Dict[str, Any]]
    table: Optional[List[Dict[str, Any]]]
    commentary: str

    # 错误信息
    error: Optional[str]

    # Debug 信息
    debug: Optional[Dict[str, Any]]


# ============================================================================
# 节点函数（增强版：带打印信息）
# ============================================================================

def router_node(state: GraphState) -> GraphState:
    """路由节点：判断查询类型"""

    print(f"\n{'='*80}")
    print(f"[1/8 Router] 开始执行路由判断")
    print(f"[1/8 Router] 用户输入: {state.get('user_message', '')[:80]}...")

    # TODO: 实现路由逻辑
    state["query_type"] = "market_query"  # 占位

    print(f"[1/8 Router] ✓ 判断完成: query_type = {state['query_type']}")
    return state


def plan_gen_node(state: GraphState) -> GraphState:
    """计划生成节点：NL → QueryPlan"""

    print(f"\n{'='*80}")
    print(f"[2/8 PlanGen] 开始生成 QueryPlan")

    user_message = state.get("user_message", "")

    # Mock implementation: Generate QueryPlan based on keywords
    # TODO: Replace with actual LLM call when vLLM service is available
    print(f"[2/8 PlanGen] 分析用户问题: {user_message[:80]}...")

    # Simple rule-based mapping for testing
    if "涨幅" in user_message or "上涨" in user_message:
        state["query_plan"] = {
            "query_type": "basic",
            "date": state.get("default_date", "20250115"),
            "market": state.get("default_market", "ALL"),
            "metrics": ["涨幅"],
            "filters": [],
            "order_by": [{"field": "涨幅", "desc": True}],
            "limit": 10,
            "output_fields": ["SecurityID", "ClosePx", "PreClosePx", "涨幅"],
        }
    elif "成交额" in user_message or "成交量" in user_message:
        state["query_plan"] = {
            "query_type": "basic",
            "date": state.get("default_date", "20250115"),
            "market": state.get("default_market", "ALL"),
            "metrics": [],
            "filters": [],
            "order_by": [{"field": "TotalValueTrade", "desc": True}],
            "limit": 10,
            "output_fields": ["SecurityID", "ClosePx", "TotalValueTrade", "TotalVolumeTrade"],
        }
    elif "振幅" in user_message:
        state["query_plan"] = {
            "query_type": "basic",
            "date": state.get("default_date", "20250115"),
            "market": state.get("default_market", "ALL"),
            "metrics": ["振幅"],
            "filters": [],
            "order_by": [{"field": "振幅", "desc": True}],
            "limit": 10,
            "output_fields": ["SecurityID", "ClosePx", "HighPx", "LowPx", "振幅"],
        }
    else:
        # Default: 涨幅查询
        state["query_plan"] = {
            "query_type": "basic",
            "date": state.get("default_date", "20250115"),
            "market": state.get("default_market", "ALL"),
            "metrics": ["涨幅"],
            "filters": [],
            "order_by": [{"field": "涨幅", "desc": True}],
            "limit": 10,
            "output_fields": ["SecurityID", "ClosePx", "PreClosePx", "涨幅"],
        }

    print(f"[2/8 PlanGen] ✓ QueryPlan 生成完成（Mock 模式）")
    print(f"[2/8 PlanGen]   - query_type: {state['query_plan']['query_type']}")
    print(f"[2/8 PlanGen]   - date: {state['query_plan']['date']}")
    print(f"[2/8 PlanGen]   - market: {state['query_plan']['market']}")
    print(f"[2/8 PlanGen]   - limit: {state['query_plan']['limit']}")

    return state


def validate_node(state: GraphState) -> GraphState:
    """校验节点：Schema + 白名单 + 业务规则校验"""

    print(f"\n{'='*80}")
    print(f"[3/8 Validate] 开始校验 QueryPlan")

    # TODO: 实现校验逻辑
    state["validation_errors"] = None  # 占位

    if state["validation_errors"]:
        print(f"[3/8 Validate] ✗ 校验失败，发现 {len(state['validation_errors'])} 个错误")
        for i, err in enumerate(state["validation_errors"], 1):
            print(f"[3/8 Validate]   {i}. {err}")
    else:
        print(f"[3/8 Validate] ✓ 校验通过")

    return state


def repair_node(state: GraphState) -> GraphState:
    """修复节点：校验失败时让 LLM 修复"""

    print(f"\n{'='*80}")
    print(f"[4/8 Repair] 开始修复 QueryPlan")
    print(f"[4/8 Repair] 重试次数: {state.get('retry_count', 0)}/2")

    # TODO: 实现修复逻辑
    state["retry_count"] = state.get("retry_count", 0) + 1

    print(f"[4/8 Repair] ✓ 修复完成")

    return state


def execute_node(state: GraphState) -> GraphState:
    """执行节点：QueryPlan → SQL → DuckDB → DataFrame"""

    print(f"\n{'='*80}")
    print(f"[5/8 Execute] 开始执行 SQL 查询")

    try:
        import duckdb
        from core.sql_compiler import SQLCompilerEnhanced

        # 1. 解析 Parquet 路径
        print(f"[5/8 Execute] 解析数据文件路径...")
        parquet_paths = ["data/test.parquet"]  # 使用 mock 数据

        # 2. 编译 SQL
        print(f"[5/8 Execute] 编译 QueryPlan → SQL...")
        compiler = SQLCompilerEnhanced()
        sql = compiler.compile(state["query_plan"], parquet_paths)
        state["sql"] = sql

        # 3. 执行 DuckDB 查询
        print(f"[5/8 Execute] 执行 DuckDB 查询...")
        conn = duckdb.connect(":memory:")
        result = conn.execute(sql).fetchdf()
        state["dataframe"] = result
        conn.close()

        print(f"[5/8 Execute] ✓ 查询完成")
        print(f"[5/8 Execute]   - SQL 长度: {len(state['sql'])} 字符")
        print(f"[5/8 Execute]   - 返回行数: {len(result)}")

    except Exception as e:
        print(f"[5/8 Execute] ✗ 查询失败: {e}")
        state["error"] = str(e)
        state["dataframe"] = None

    return state


def postprocess_node(state: GraphState) -> GraphState:
    """后处理节点：格式化 + 统计摘要"""

    print(f"\n{'='*80}")
    print(f"[6/8 PostProcess] 开始后处理")

    try:
        df = state.get("dataframe")

        if df is not None and not df.empty:
            # 转换 DataFrame 为字典列表
            state["table"] = df.to_dict(orient='records')

            # 生成统计摘要
            state["summary"] = {
                "总记录数": len(df),
                "列数": len(df.columns),
                "列名": list(df.columns),
            }

            print(f"[6/8 PostProcess] ✓ 后处理完成")
            print(f"[6/8 PostProcess]   - 输出记录数: {len(state['table'])}")
            print(f"[6/8 PostProcess]   - 统计摘要: {state['summary']}")
        else:
            state["table"] = []
            state["summary"] = {"总记录数": 0}
            print(f"[6/8 PostProcess] ⚠ 数据为空")

    except Exception as e:
        print(f"[6/8 PostProcess] ✗ 后处理失败: {e}")
        state["table"] = []
        state["summary"] = {"总记录数": 0, "错误": str(e)}

    return state


def narrate_node(state: GraphState) -> GraphState:
    """解读节点：生成专业解读"""

    print(f"\n{'='*80}")
    print(f"[7/8 Narrate] 开始生成解读")
    print(f"[7/8 Narrate] 调用 LLM 生成专业解读...")

    # TODO: 实现解读逻辑
    state["commentary"] = f"根据查询结果，共找到 {state['summary'].get('总记录数', 0)} 条记录。（待实现完整解读）"  # 占位

    print(f"[7/8 Narrate] ✓ 解读生成完成")
    print(f"[7/8 Narrate]   - 解读长度: {len(state['commentary'])} 字符")
    print(f"[7/8 Narrate]   - 解读预览: {state['commentary'][:80]}...")

    return state


def memory_update_node(state: GraphState) -> GraphState:
    """记忆更新节点：更新会话状态"""

    print(f"\n{'='*80}")
    print(f"[8/8 MemoryUpdate] 开始更新会话状态")

    # TODO: 实现记忆更新逻辑

    print(f"[8/8 MemoryUpdate] ✓ 会话状态更新完成")
    print(f"[8/8 MemoryUpdate]   - 历史记录数: {len(state.get('history', []))}")
    print(f"{'='*80}\n")

    return state


# ============================================================================
# 条件边：决定状态流转
# ============================================================================

def should_repair(state: GraphState) -> str:
    """判断是否需要修复"""

    if state.get("validation_errors"):
        if state.get("retry_count", 0) < 2:
            print(f"[Condition] 校验失败，进入 Repair 节点")
            return "repair"
        else:
            print(f"[Condition] 重试次数用尽，返回错误")
            return "error"

    print(f"[Condition] 校验通过，进入 Execute 节点")
    return "execute"


def route_by_query_type(state: GraphState) -> str:
    """根据查询类型路由"""

    query_type = state.get("query_type", "market_query")

    if query_type == "chitchat":
        print(f"[Condition] 闲聊查询，直接返回")
        return "chitchat"
    elif query_type == "field_explain":
        print(f"[Condition] 字段解释查询，直接返回")
        return "field_explain"
    else:
        print(f"[Condition] 行情查询，进入 PlanGen 节点")
        return "plan_gen"


# ============================================================================
# 构建 LangGraph
# ============================================================================

def build_graph() -> StateGraph:
    """构建 LangGraph 状态机（增强版）"""

    print("\n[Graph] 开始构建 LangGraph 状态机...")

    # 创建图
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("router", router_node)
    workflow.add_node("plan_gen", plan_gen_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("repair", repair_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("postprocess", postprocess_node)
    workflow.add_node("narrate", narrate_node)
    workflow.add_node("memory_update", memory_update_node)

    # 设置入口点
    workflow.set_entry_point("router")

    # 添加条件边：router → [plan_gen | chitchat | field_explain]
    workflow.add_conditional_edges(
        "router",
        route_by_query_type,
        {
            "plan_gen": "plan_gen",
            "chitchat": END,
            "field_explain": END,
        }
    )

    # 添加边：plan_gen → validate
    workflow.add_edge("plan_gen", "validate")

    # 添加条件边：validate → [execute | repair | error]
    workflow.add_conditional_edges(
        "validate",
        should_repair,
        {
            "execute": "execute",
            "repair": "repair",
            "error": END,
        }
    )

    # 添加边：repair → validate（重新校验）
    workflow.add_edge("repair", "validate")

    # 添加边：execute → postprocess → narrate → memory_update → END
    workflow.add_edge("execute", "postprocess")
    workflow.add_edge("postprocess", "narrate")
    workflow.add_edge("narrate", "memory_update")
    workflow.add_edge("memory_update", END)

    # 编译图
    print("[Graph] ✓ LangGraph 状态机构建完成\n")
    return workflow.compile()


# ============================================================================
# 导出
# ============================================================================

# 创建全局图实例
graph = build_graph()


# ============================================================================
# 测试入口
# ============================================================================

if __name__ == "__main__":
    print("="*80)
    print("测试 LangGraph 工作流")
    print("="*80)

    # 测试状态流转
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
    print(f"  - query_type: {result.get('query_type')}")
    print(f"  - query_plan: {result.get('query_plan') is not None}")
    print(f"  - sql: {result.get('sql') is not None}")
    print(f"  - table: {len(result.get('table', []))} 行")
    print(f"  - commentary: {result.get('commentary', '')[:100]}...")
