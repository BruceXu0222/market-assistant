"""
MemoryUpdate 节点：记忆更新
==========================

功能：
1. 更新会话默认日期/市场（如果用户指定了）
2. 更新对话历史
3. 学习用户偏好

示例：
- 用户说"查询上交所数据"，则更新 default_market = "XSHG"
- 用户说"查询2025年1月15日的数据"，则更新 default_date = "20250115"

偏好学习（可选）：
- 统计用户常用的查询类型（TopK/筛选/排序）
- 统计用户常用的字段
- 个性化 Prompt
"""

from typing import Dict, Any

# ============================================================================
# 记忆更新函数
# ============================================================================

def memory_update_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    记忆更新节点：更新会话状态

    Args:
        state: LangGraph 状态

    Returns:
        state: 更新后的状态（包含 default_date, default_market, history）

    TODO:
    1. 更新默认日期/市场
    2. 更新对话历史
    3. 学习用户偏好（可选）
    4. 添加日志
    """

    query_plan = state.get("query_plan", {})

    # ========================================================================
    # 1. 更新默认日期（如果用户明确指定了）
    # ========================================================================

    # TODO: 判断用户是否明确指定了日期（而不是使用默认值）
    # 简化实现：如果 query_plan 中的 date 与 default_date 不同，则更新
    # plan_date = query_plan.get("date")
    # if plan_date and plan_date != state.get("default_date"):
    #     state["default_date"] = plan_date
    #     logger.info(f"[MemoryUpdate] 更新默认日期: {plan_date}")

    # ========================================================================
    # 2. 更新默认市场（如果用户明确指定了）
    # ========================================================================

    # TODO: 同上
    # plan_market = query_plan.get("market")
    # if plan_market and plan_market != "ALL" and plan_market != state.get("default_market"):
    #     state["default_market"] = plan_market
    #     logger.info(f"[MemoryUpdate] 更新默认市场: {plan_market}")

    # ========================================================================
    # 3. 更新对话历史
    # ========================================================================

    # TODO: 添加到历史记录
    # history_entry = {
    #     "user": state.get("user_message", ""),
    #     "assistant": state.get("commentary", ""),
    #     "query_plan": query_plan,
    #     "timestamp": datetime.now().isoformat(),
    # }
    # state.setdefault("history", []).append(history_entry)

    # ========================================================================
    # 4. 学习用户偏好（可选，高级功能）
    # ========================================================================

    # TODO: 统计用户常用的查询类型、字段等
    # 例如：
    # - 统计 query_type 分布
    # - 统计常用字段（filters/order_by）
    # - 存储到用户画像

    # ========================================================================
    # 日志记录
    # ========================================================================

    # TODO: 添加日志
    # logger.info(f"[MemoryUpdate] session={state['session_id']}, history_count={len(state['history'])}")

    return state
