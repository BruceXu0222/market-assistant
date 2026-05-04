"""
Validate 节点：计划校验（简化版）
================================

功能：
1. 检查 LLM 生成的计划是否有效
2. 验证已在 LLMQueryPlanner 中完成，这里主要做最终检查
3. 决定是否需要修复（repair）

由于验证逻辑已集成到 llm_planner.py 中，此节点主要作为：
- 验证结果的传递
- 决定下一步流程（execute 或 repair）
"""

from typing import Dict, Any, List


def validate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    校验节点：检查 query_plan 是否有效

    Args:
        state: LangGraph 状态

    Returns:
        state: 更新后的状态（包含 validation_errors 判断结果）
    """

    query_plan = state.get("query_plan")
    validation_errors = state.get("validation_errors")

    # 如果 query_plan 为空，这是严重错误
    if not query_plan:
        if not validation_errors:
            state["validation_errors"] = ["QueryPlan 为空"]
        return state

    # 如果 query_plan 包含 error 字段，说明 LLM 调用失败
    if "error" in query_plan:
        if not validation_errors:
            state["validation_errors"] = [query_plan["error"]]
        return state

    # 验证已在 LLMQueryPlanner 中完成
    # 这里可以做额外的业务逻辑检查

    # 检查必要字段
    errors = validation_errors or []

    if not query_plan.get("date"):
        errors.append("缺少日期字段")

    if not query_plan.get("market"):
        errors.append("缺少市场字段")

    # 如果没有任何输出字段和聚合，添加默认
    if not query_plan.get("select_fields") and not query_plan.get("aggregations"):
        # 添加默认输出字段
        query_plan["select_fields"] = ["SecurityID", "ClosePx", "PreClosePx"]

    # 更新验证错误
    state["validation_errors"] = errors if errors else None

    # 日志
    session_id = state.get("session_id", "unknown")
    if errors:
        print(f"[Validate] session={session_id}, errors={errors}")
    else:
        print(f"[Validate] session={session_id}, 校验通过")

    return state


def should_repair(state: Dict[str, Any]) -> str:
    """
    条件判断：是否需要修复

    Returns:
        "repair" 如果需要修复
        "execute" 如果可以执行
        "end" 如果重试次数已用完
    """

    validation_errors = state.get("validation_errors")
    retry_count = state.get("retry_count", 0)

    if not validation_errors:
        return "execute"

    if retry_count >= 2:
        print(f"[Validate] 重试次数已达上限 ({retry_count})")
        return "end"

    return "repair"
