"""
PlanGen 节点：LLM 驱动的计划生成
================================

功能：
1. 调用 LLM 将自然语言转换为 QueryPlan（JSON）
2. 使用 LLMQueryPlanner 进行灵活的计划生成
3. 内置验证和默认值处理

与旧版区别：
- 不再依赖固定的 Pydantic schema（plan_schema.py）
- LLM 可以生成更灵活的查询结构
- 验证逻辑集成在 planner 中
"""

from typing import Dict, Any
from datetime import datetime, timedelta

from core.llm_planner import LLMQueryPlanner, generate_query_plan
from core.llm_client import LLMClient


# ============================================================================
# 计划生成节点
# ============================================================================

def plan_gen_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    计划生成节点：NL → QueryPlan（LLM 驱动）

    Args:
        state: LangGraph 状态，包含：
            - user_message: 用户输入
            - default_date: 默认日期（可选）
            - default_market: 默认市场（可选）
            - session_id: 会话 ID
            - history: 对话历史（可选）

    Returns:
        state: 更新后的状态，包含：
            - query_plan: 生成的查询计划
            - validation_errors: 验证错误（如果有）
            - error: 严重错误信息（如果有）
    """

    user_message = state.get("user_message", "")
    default_date = state.get("default_date")
    default_market = state.get("default_market", "ALL")
    history = state.get("history", [])

    # ========================================================================
    # 处理默认日期
    # ========================================================================

    if not default_date:
        # 默认使用昨天（假设今天数据还未生成）
        yesterday = datetime.now() - timedelta(days=1)
        default_date = yesterday.strftime("%Y%m%d")

    # ========================================================================
    # 构建上下文（用于多轮对话）
    # ========================================================================

    context = None
    if history:
        # 只取最近几轮对话作为上下文
        recent_history = history[-3:] if len(history) > 3 else history
        context = {"recent_queries": recent_history}

    # ========================================================================
    # 调用 LLM Planner 生成查询计划
    # ========================================================================

    try:
        # 使用 LLMQueryPlanner
        planner = LLMQueryPlanner()
        query_plan, validation_errors = planner.generate_plan(
            user_query=user_message,
            default_date=default_date,
            default_market=default_market,
            context=context,
        )

        state["query_plan"] = query_plan
        state["validation_errors"] = validation_errors if validation_errors else None

        # 如果有验证错误，记录但不阻止（可以在后续节点修复）
        if validation_errors:
            print(f"[PlanGen] 验证警告: {validation_errors}")

    except Exception as e:
        # 严重错误：无法生成计划
        state["error"] = f"计划生成失败: {str(e)}"
        state["query_plan"] = None
        state["validation_errors"] = [str(e)]
        print(f"[PlanGen] 错误: {e}")

    # ========================================================================
    # 日志记录
    # ========================================================================

    session_id = state.get("session_id", "unknown")
    print(f"[PlanGen] session={session_id}, plan={state.get('query_plan')}")

    return state


# ============================================================================
# 辅助函数：用于测试或直接调用
# ============================================================================

def generate_plan_from_query(
    query: str,
    date: str = None,
    market: str = "ALL",
) -> Dict[str, Any]:
    """
    从查询生成计划的便捷函数

    Args:
        query: 用户查询
        date: 日期（YYYYMMDD）
        market: 市场代码

    Returns:
        query_plan: 查询计划字典
    """
    plan, errors = generate_query_plan(query, date, market)
    if errors:
        plan["_validation_errors"] = errors
    return plan


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("PlanGen Node Test")
    print("=" * 60)

    # 模拟 state
    test_state = {
        "session_id": "test-001",
        "user_message": "今天涨幅前10的股票有哪些？",
        "default_date": "20250115",
        "default_market": "ALL",
        "history": [],
    }

    print(f"输入: {test_state['user_message']}")
    print("-" * 40)

    # 调用节点
    result_state = plan_gen_node(test_state)

    print(f"查询计划: {result_state.get('query_plan')}")
    print(f"验证错误: {result_state.get('validation_errors')}")
    print(f"错误: {result_state.get('error')}")
