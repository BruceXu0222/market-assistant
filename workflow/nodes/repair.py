"""
Repair 节点：计划修复
====================

功能：
1. 将 validation_errors 反馈给 LLM
2. 让 LLM 输出 JSON patch 修复
3. 应用 patch 更新 query_plan
4. 增加 retry_count

修复策略：
- 方案1：让 LLM 重新生成完整的 QueryPlan
- 方案2：让 LLM 只输出需要修改的部分（JSON patch）
- MVP 建议：方案1（更简单）

Prompt 设计：
- 原始 QueryPlan
- 校验错误列表
- 要求：修复错误并重新输出 QueryPlan
"""

from typing import Dict, Any
import json

# TODO: from core.llm_client import LLMClient
# TODO: from core.configs.prompts import load_prompt

# ============================================================================
# Prompt 模板（待移至 configs/prompts/plan_repair.txt）
# ============================================================================

REPAIR_SYSTEM_PROMPT = """
You are a QueryPlan repair assistant. Fix the QueryPlan according to validation errors.

Repair rules:
1. Only fix the issues mentioned in the errors.
2. Follow the allowed fields and business rules.
3. Output valid JSON.
4. Output the repaired QueryPlan only, with no extra prose.

Allowed fields:
- Market, MDDate, SecurityID, Symbol, HTSCSecurityID
- OpenPx, ClosePx, HighPx, LowPx, PreClosePx, LastPx
- TotalValueTrade, TotalVolumeTrade, ChangePx, ChangePct, Amplitude, TurnoverRate
- 涨幅, 跌幅, 振幅, 换手率

Allowed markets: HK, US, ALL
Allowed operators: >, <, =, >=, <=, !=
"""


# ============================================================================
# 修复函数
# ============================================================================

def repair_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    修复节点：校验失败时让 LLM 修复

    Args:
        state: LangGraph 状态

    Returns:
        state: 更新后的状态（包含修复后的 query_plan 和 retry_count）

    TODO:
    1. 构建修复 Prompt
    2. 调用 LLM 生成修复后的 QueryPlan
    3. 解析并更新 query_plan
    4. 增加 retry_count
    5. 添加日志
    """

    query_plan = state.get("query_plan")
    validation_errors = state.get("validation_errors", [])

    # ========================================================================
    # 构建修复 Prompt
    # ========================================================================

    prompt = f"""
{REPAIR_SYSTEM_PROMPT}

Original QueryPlan:
{json.dumps(query_plan, ensure_ascii=False, indent=2)}

Validation errors:
{chr(10).join(f"- {error}" for error in validation_errors)}

Return the repaired QueryPlan as JSON only:
"""

    # ========================================================================
    # 调用 LLM
    # ========================================================================

    # TODO: 实现 LLM 调用
    # llm_client = LLMClient()
    # response = llm_client.chat(
    #     prompt,
    #     temperature=0.1,  # 更低的温度保证稳定性
    #     max_tokens=512,
    # )

    # 占位：模拟修复（这里简单地返回原 plan，实际应修复）
    response = json.dumps(query_plan, ensure_ascii=False)

    # ========================================================================
    # 解析修复后的 QueryPlan
    # ========================================================================

    try:
        repaired_plan = json.loads(response)
        state["query_plan"] = repaired_plan
        state["validation_errors"] = None  # 清空错误（待重新校验）
    except json.JSONDecodeError as e:
        # 修复失败，保留原错误
        state["error"] = f"QueryPlan 修复失败: {e}"

    # ========================================================================
    # 增加重试次数
    # ========================================================================

    state["retry_count"] = state.get("retry_count", 0) + 1

    # ========================================================================
    # 日志记录
    # ========================================================================

    # TODO: 添加日志
    # logger.info(f"[Repair] session={state['session_id']}, retry_count={state['retry_count']}")

    return state
